from datetime import date
from io import BytesIO
from io import StringIO
import tempfile
from unittest.mock import patch
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils.datastructures import MultiValueDict
from django.urls import reverse
from .models import DisplayConfiguration, Employee, EmployeePhoto
from .forms import EmployeeForm
from .views import birthdays_for, import_preview

class DemoDataCommandTests(TestCase):
    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_demo_data_command_is_idempotent_and_includes_scenarios(self, _today):
        call_command("load_demo_data", stdout=StringIO())
        call_command("load_demo_data", stdout=StringIO())
        self.assertEqual(Employee.objects.filter(employee_id__startswith="DEMO-").count(), 3)
        self.assertEqual(Employee.objects.get(employee_id="DEMO-TODAY").date_of_birth.strftime("%m-%d"), "11-13")

class BirthdayLogicTests(TestCase):
    def make_employee(self, employee_id, dob, active=True):
        return Employee.objects.create(employee_id=employee_id, name=employee_id, date_of_birth=dob, is_active=active)

    def test_multiple_birthdays_match_month_and_day_only(self):
        first = self.make_employee("E1", date(1980, 5, 14))
        second = self.make_employee("E2", date(1998, 5, 14))
        self.make_employee("E3", date(1980, 5, 15))
        self.assertEqual(list(birthdays_for(date(2026, 5, 14))), [first, second])

    def test_inactive_employee_is_excluded(self):
        self.make_employee("E1", date(1980, 5, 14), active=False)
        self.assertEqual(birthdays_for(date(2026, 5, 14)).count(), 0)

    def test_february_29_uses_february_28_on_non_leap_years(self):
        employee = self.make_employee("LEAP", date(2000, 2, 29))
        self.assertEqual(list(birthdays_for(date(2025, 2, 28))), [employee])
        self.assertEqual(list(birthdays_for(date(2024, 2, 28))), [])
        self.assertEqual(list(birthdays_for(date(2024, 2, 29))), [employee])

    @patch("employees.views.timezone.localdate", return_value=date(2026, 6, 2))
    def test_public_display_has_safe_empty_state(self, _today):
        response = self.client.get(reverse("display_birthdays"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wishing everyone a wonderful day.")
        self.assertNotContains(response, "date_of_birth")

    @patch("employees.views.timezone.localdate", return_value=date(2026, 5, 14))
    def test_public_display_does_not_render_birth_year(self, _today):
        self.make_employee("E1", date(1980, 5, 14))
        response = self.client.get(reverse("display_birthdays"))
        self.assertContains(response, "E1")
        self.assertNotContains(response, "1980")

class EmployeeAdminFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="operator", password="strong-test-password")
        self.client.force_login(self.user)

    def test_employee_edit_requires_explicit_permission(self):
        response = self.client.get(reverse("employee_add"))
        self.assertEqual(response.status_code, 403)
        permission = Permission.objects.get(codename="add_employee")
        self.user.user_permissions.add(permission)
        response = self.client.get(reverse("employee_add"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmployeeForm().fields["section"].label, "Section")

    def test_section_csv_column_imports_and_legacy_department_is_accepted(self):
        valid, errors = import_preview([{"employee_id": "SECTION1", "name": "Taylor Reed", "section": "Traction", "date_of_birth": "1991-03-12"}])
        self.assertEqual(errors, [])
        self.assertEqual(valid[0]["section"], "Traction")
        legacy, errors = import_preview([{"employee_id": "SECTION2", "name": "Alex Morgan", "department": "Stores", "date_of_birth": "1992-04-20"}])
        self.assertEqual(errors, [])
        self.assertEqual(legacy[0]["section"], "Stores")

    def test_employee_templates_use_section_header(self):
        self.allow("add_employee")
        csv_response = self.client.get(reverse("employee_template"))
        self.assertContains(csv_response, "section")
        self.assertNotContains(csv_response, "department")
        from openpyxl import load_workbook
        workbook = load_workbook(BytesIO(self.client.get(reverse("employee_template_xlsx")).content), read_only=True)
        self.assertEqual(next(workbook.active.values)[3], "section")

    def test_import_preview_flags_bad_date_and_duplicate_ids(self):
        rows = [
            {"employee_id": "X1", "name": "One", "date_of_birth": "not-a-date"},
            {"employee_id": "X1", "name": "Two", "date_of_birth": "1990-01-02"},
        ]
        valid, errors = import_preview(rows)
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 2)
        self.assertIn("Invalid date_of_birth (use YYYY-MM-DD)", errors[0]["errors"])
        self.assertIn("Duplicate ID in file", errors[1]["errors"])

    def test_display_settings_require_permission_and_save(self):
        permission = Permission.objects.get(codename="manage_displayconfiguration")
        self.user.user_permissions.add(permission)
        response = self.client.post(reverse("display_settings"), {"organization_name": "Example Group", "office_name": "North Office", "birthday_greeting": "Enjoy your special day!", "slide_duration": 12, "theme": "minimal", "transition": "fade", "timezone_name": "Asia/Kolkata", "date_format": "weekday", "refresh_interval": 60, "empty_title": "Welcome", "empty_message": "Have a good day", "leap_day_policy": "feb28"})
        self.assertEqual(response.status_code, 302)
        config = DisplayConfiguration.objects.get()
        self.assertEqual(config.office_name, "North Office")
        self.assertEqual(config.slide_duration, 12)
        self.assertEqual(config.theme, "minimal")

    def allow(self, *codenames):
        for codename in codenames:
            self.user.user_permissions.add(Permission.objects.get(codename=codename))

    def test_csv_import_preview_error_report_and_confirm(self):
        self.allow("add_employee")
        upload = SimpleUploadedFile("employees.csv", b"employee_id,name,date_of_birth,section\nC1,Casey Lee,1990-04-05,Operations\nC2,Invalid Person,not-a-date,Finance\n")
        preview = self.client.post(reverse("employee_import"), {"file": upload})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Invalid date_of_birth")
        report = self.client.get(reverse("employee_import_errors"))
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"C2", report.content)
        result = self.client.post(reverse("employee_import_confirm"), {})
        self.assertEqual(result.status_code, 200)
        self.assertIn("text/csv", result["Content-Type"])
        self.assertTrue(Employee.objects.filter(employee_id="C1").exists())
        self.assertFalse(Employee.objects.filter(employee_id="C2").exists())

    def test_xlsx_import_preview(self):
        from openpyxl import Workbook
        file_data = BytesIO(); workbook = Workbook(); sheet = workbook.active
        sheet.append(["employee_id", "name", "date_of_birth"]); sheet.append(["XLS1", "Alex Morgan", date(1992, 7, 8)])
        workbook.save(file_data)
        upload = SimpleUploadedFile("employees.xlsx", file_data.getvalue())
        self.allow("add_employee")
        response = self.client.post(reverse("employee_import"), {"file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex Morgan")

    def test_create_and_deactivate_employee_through_views(self):
        self.allow("add_employee", "change_employee")
        response = self.client.post(reverse("employee_add"), {"employee_id": "CRUD1", "name": "Taylor Reed", "designation": "Engineer", "section": "Works", "date_of_birth": "1991-03-12", "is_active": "on"})
        self.assertEqual(response.status_code, 302)
        employee = Employee.objects.get(employee_id="CRUD1")
        self.assertTrue(employee.is_active)
        response = self.client.post(reverse("employee_deactivate", args=[employee.pk]))
        employee.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(employee.is_active)

    def test_employee_form_saves_multiple_additional_photos(self):
        image_data = BytesIO()
        from PIL import Image
        Image.new("RGB", (40, 40), "navy").save(image_data, format="JPEG")
        jpeg = image_data.getvalue()
        uploads = MultiValueDict({"additional_photos": [
            SimpleUploadedFile("first.jpg", jpeg, content_type="image/jpeg"),
            SimpleUploadedFile("second.jpg", jpeg, content_type="image/jpeg"),
        ]})
        with tempfile.TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            form = EmployeeForm(
                data={"employee_id": "MULTI1", "name": "Photo Person", "date_of_birth": "1990-05-14", "is_active": "on"},
                files=uploads,
            )
            self.assertTrue(form.is_valid(), form.errors)
            employee = form.save()
            self.assertEqual(employee.gallery_photos.count(), 2)

    def test_import_handles_600_employee_csv(self):
        self.allow("add_employee")
        data = ["employee_id,name,date_of_birth,section"]
        data.extend(f"BULK{i:04d},Employee {i},1990-01-01,Operations" for i in range(600))
        upload = SimpleUploadedFile("six-hundred.csv", ("\n".join(data) + "\n").encode())
        preview = self.client.post(reverse("employee_import"), {"file": upload})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(len(self.client.session["employee_import_rows"]), 600)
        confirmed = self.client.post(reverse("employee_import_confirm"), {})
        self.assertEqual(confirmed.status_code, 302)
        self.assertEqual(Employee.objects.count(), 600)

    def test_existing_rows_are_skipped_or_require_change_permission_to_update(self):
        employee = Employee.objects.create(employee_id="EXIST1", name="Original Name", date_of_birth=date(1980, 1, 1))
        self.allow("add_employee")
        def preview_update():
            csv_data = b"employee_id,name,date_of_birth\nEXIST1,Updated Name,1985-02-03\n"
            return self.client.post(reverse("employee_import"), {"file": SimpleUploadedFile("update.csv", csv_data)})
        preview_update()
        skipped = self.client.post(reverse("employee_import_confirm"), {})
        self.assertEqual(skipped.status_code, 302)
        employee.refresh_from_db()
        self.assertEqual(employee.name, "Original Name")
        preview_update()
        denied = self.client.post(reverse("employee_import_confirm"), {"update_existing": "yes"})
        self.assertEqual(denied.status_code, 403)
        self.allow("change_employee")
        updated = self.client.post(reverse("employee_import_confirm"), {"update_existing": "yes"})
        self.assertEqual(updated.status_code, 302)
        employee.refresh_from_db()
        self.assertEqual(employee.name, "Updated Name")

