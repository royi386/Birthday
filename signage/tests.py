import tempfile
from io import BytesIO
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from employees.models import DisplayConfiguration, Employee, EmployeePhoto
from .forms import DisplayOffScheduleForm
from .models import Announcement, AuditLog, ContentSchedule, DisplayDevice, DisplayHoliday, DisplayOffSchedule, FullScreenPhoto, GeneralMessage, LocomotiveType, Recognition, SafetyMessage
from .services import build_display_items, display_off_active, display_payload, upcoming_anniversaries

class SchedulerTests(TestCase):
    def setUp(self):
        self.config = DisplayConfiguration.objects.create(organization_name="Example Group", office_name="Main Office")

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_scheduler_rotates_birthday_safety_recognition_announcement_and_general(self, _today):
        Employee.objects.create(employee_id="TODAY1", name="Birthday Person", date_of_birth=date(1990, 11, 13), is_active=True)
        employee = Employee.objects.create(employee_id="RECOG1", name="Award Person", date_of_birth=date(1988, 1, 2))
        Recognition.objects.create(employee=employee, title="Great work", message="Thanks for the contribution.", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        now = timezone.now()
        Announcement.objects.create(title="Town hall", description="Starts at noon", starts_at=now-timedelta(minutes=5), ends_at=now+timedelta(hours=2))
        Announcement.objects.create(title="Expired notice", description="Old", starts_at=now-timedelta(days=2), ends_at=now-timedelta(days=1))
        SafetyMessage.objects.create(title="Wear eye protection", message="Use approved eye protection.", category="workplace", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        GeneralMessage.objects.create(title="Office hours", message="Reception opens at nine.", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        result = build_display_items(self.config)
        categories = [item["category"] for item in result]
        for required in ("birthday", "safety", "recognition", "announcement", "general"):
            self.assertIn(required, categories)
        self.assertNotIn("Expired notice", [item["title"] for item in result])
        self.assertLess(categories.index("birthday"), categories.index("safety"))
        self.assertEqual(result[0]["name"], "Birthday Person")

    @patch("signage.services.office_today", return_value=date(2026, 2, 28))
    def test_leap_day_policy_can_shift_birthday_to_march_first(self, _today):
        self.config.leap_day_policy = "mar1"; self.config.save()
        Employee.objects.create(employee_id="LEAP1", name="Leap Employee", date_of_birth=date(2000, 2, 29))
        items = build_display_items(self.config)
        self.assertEqual([item["name"] for item in items if item["category"] == "birthday"], ["Leap Employee"])
        birthday = next(item for item in items if item["category"] == "birthday")
        self.assertEqual(birthday["title"], "Advance Happy Birthday!")

    @patch("signage.services.office_today", return_value=date(2026, 3, 1))
    def test_leap_day_policy_applies_to_work_anniversaries(self, _today):
        self.config.leap_day_policy = "mar1"
        self.config.anniversary_milestones = "6"
        self.config.save()
        Employee.objects.create(employee_id="LEAPANN", name="Leap Joiner", date_of_birth=date(1990, 1, 1), date_of_joining=date(2020, 2, 29))
        items = build_display_items(self.config)
        self.assertTrue(any(item["category"] == "anniversary" and item["name"] == "Leap Joiner" for item in items))

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_anniversary_milestones_and_upcoming_date(self, _today):
        self.config.anniversary_milestones = "1,5"; self.config.save()
        Employee.objects.create(employee_id="ANN1", name="Five Year Employee", date_of_birth=date(1990, 3, 3), date_of_joining=date(2021, 11, 20))
        Employee.objects.create(employee_id="ANN2", name="No Joining Date", date_of_birth=date(1990, 3, 4))
        upcoming = upcoming_anniversaries(self.config, horizon_days=31)
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0]["employee"].employee_id, "ANN1")
        self.assertEqual(upcoming[0]["years"], 5)
        with patch("signage.services.office_today", return_value=date(2026, 11, 20)):
            items = build_display_items(self.config)
        self.assertTrue(any(item["category"] == "anniversary" for item in items))

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_category_can_be_disabled(self, _today):
        ContentSchedule.objects.filter(category="safety").update(enabled=False)
        SafetyMessage.objects.create(title="Safety test", message="Test", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        self.assertNotIn("safety", [item["category"] for item in build_display_items(self.config)])

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_category_duration_is_used_when_content_has_no_override(self, _today):
        ContentSchedule.objects.filter(category="safety").update(duration=22)
        SafetyMessage.objects.create(title="Safety duration", message="Read carefully", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        slide = next(item for item in build_display_items(self.config) if item["category"] == "safety")
        self.assertEqual(slide["duration"], 22)

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_birthday_slideshow_rotates_each_employee_photo(self, _today):
        from PIL import Image
        image_data = BytesIO()
        Image.new("RGB", (40, 40), "navy").save(image_data, format="JPEG")
        jpeg = image_data.getvalue()
        with tempfile.TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            person = Employee.objects.create(employee_id="GALLERY1", name="Gallery Person", date_of_birth=date(1990, 11, 13))
            EmployeePhoto.objects.create(employee=person, photo=SimpleUploadedFile("one.jpg", jpeg, content_type="image/jpeg"))
            EmployeePhoto.objects.create(employee=person, photo=SimpleUploadedFile("two.jpg", jpeg, content_type="image/jpeg"))
            slides = [item for item in build_display_items(self.config) if item["category"] == "birthday"]
        self.assertEqual(len(slides), 2)
        self.assertEqual({item["name"] for item in slides}, {"Gallery Person"})
        self.assertNotEqual(slides[0]["image"], slides[1]["image"])

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_locomotive_population_is_daily_and_lowest_priority(self, _today):
        ContentSchedule.objects.filter(category="fleet").update(priority=1, duration=12)
        LocomotiveType.objects.create(name="WAP5", population=11)
        LocomotiveType.objects.create(name="WAP7", population=43)
        GeneralMessage.objects.create(title="Office hours", message="Open at nine", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        slides = build_display_items(self.config)
        fleet = [item for item in slides if item["category"] == "fleet"]
        self.assertEqual(len(fleet), 1)
        self.assertEqual(fleet[0]["title"], "Locomotive population")
        self.assertEqual(
            [(item["name"], item["population"]) for item in fleet[0]["locomotives"]],
            [("WAP5", 11), ("WAP7", 43)],
        )
        self.assertEqual(fleet[0]["duration"], 12)
        self.assertEqual(slides[-1]["category"], "fleet")
        self.assertEqual(ContentSchedule.objects.get(category="fleet").priority, 1)

    def test_full_screen_photos_create_individual_full_bleed_slides(self):
        from PIL import Image
        image_data = BytesIO()
        Image.new("RGB", (64, 48), "navy").save(image_data, format="JPEG")
        jpeg = image_data.getvalue()
        with tempfile.TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            FullScreenPhoto.objects.create(photo=SimpleUploadedFile("first.jpg", jpeg, content_type="image/jpeg"))
            FullScreenPhoto.objects.create(photo=SimpleUploadedFile("second.jpg", jpeg, content_type="image/jpeg"))
            slides = [item for item in build_display_items(self.config) if item["category"] == "photos"]
        self.assertEqual(len(slides), 2)
        self.assertTrue(all(item["image"].startswith("/media/full_screen_photos/") for item in slides))
        self.assertEqual({item["duration"] for item in slides}, {10})

    @patch("signage.services.office_today", return_value=date(2026, 11, 14))
    def test_sunday_birthday_is_shown_in_advance_on_saturday_only(self, _today):
        Employee.objects.create(employee_id="SUNDAY1", name="Sunday Birthday", date_of_birth=date(1990, 11, 15))
        slides = [item for item in build_display_items(self.config) if item["category"] == "birthday"]
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]["title"], "Advance Happy Birthday!")
        self.assertTrue(slides[0]["is_advance"])
        with patch("signage.services.office_today", return_value=date(2026, 11, 15)):
            self.assertFalse(any(item["category"] == "birthday" for item in build_display_items(self.config)))

    @patch("signage.services.office_today", return_value=date(2026, 11, 15))
    def test_holiday_birthday_moves_to_the_day_before(self, _today):
        Employee.objects.create(employee_id="HOLIDAY1", name="Holiday Birthday", date_of_birth=date(1990, 11, 16))
        DisplayHoliday.objects.create(name="Observed holiday", date=date(2026, 11, 16))
        birthday = next(item for item in build_display_items(self.config) if item["category"] == "birthday")
        self.assertEqual(birthday["title"], "Advance Happy Birthday!")
        self.assertEqual(birthday["subcategory"], "Advance wishes")

    def test_display_off_schedule_handles_overnight_ranges_and_selected_days(self):
        schedule = DisplayOffSchedule.objects.get(pk=1)
        schedule.schedule_enabled = True
        schedule.weekday_rules = {
            str(day): {
                "enabled": day in (0, 1),
                "start": "22:00" if day == 0 else "21:00",
                "end": "06:00" if day == 0 else "23:00",
            }
            for day in range(7)
        }
        schedule.save()
        zone = ZoneInfo("Asia/Kolkata")
        self.assertFalse(display_off_active(self.config, datetime(2026, 11, 23, 23, 0, tzinfo=zone)))
        self.assertFalse(display_off_active(self.config, datetime(2026, 11, 24, 5, 59, tzinfo=zone)))
        self.assertTrue(display_off_active(self.config, datetime(2026, 11, 24, 20, 59, tzinfo=zone)))
        self.assertFalse(display_off_active(self.config, datetime(2026, 11, 24, 22, 0, tzinfo=zone)))
        self.assertTrue(display_off_active(self.config, datetime(2026, 11, 24, 6, 0, tzinfo=zone)))
        self.assertTrue(display_off_active(self.config, datetime(2026, 11, 24, 23, 0, tzinfo=zone)))

    def test_disabled_display_on_schedule_keeps_slideshow_running(self):
        schedule = DisplayOffSchedule.objects.get(pk=1)
        schedule.schedule_enabled = False
        schedule.weekday_rules = {"0": {"enabled": True, "start": "22:00", "end": "06:00"}}
        schedule.save()
        zone = ZoneInfo("Asia/Kolkata")
        self.assertFalse(display_off_active(self.config, datetime(2026, 11, 23, 23, 0, tzinfo=zone)))

    def test_display_off_schedule_form_saves_time_and_weekdays(self):
        schedule = DisplayOffSchedule.objects.get(pk=1)
        form = DisplayOffScheduleForm({
            "display_off-schedule_enabled": "on",
            "display_off-monday_enabled": "on",
            "display_off-monday_start": "22:30",
            "display_off-monday_end": "06:15",
            "display_off-wednesday_enabled": "on",
            "display_off-wednesday_start": "21:00",
            "display_off-wednesday_end": "05:00",
        }, instance=schedule, prefix="display_off")
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue(saved.schedule_enabled)
        self.assertTrue(saved.weekday_rules["0"]["enabled"])
        self.assertEqual(saved.weekday_rules["0"]["start"], "22:30")
        self.assertTrue(saved.weekday_rules["2"]["enabled"])
        self.assertEqual(saved.weekday_rules["2"]["start"], "21:00")
        self.assertFalse(saved.weekday_rules["1"]["enabled"])

    def test_content_can_be_targeted_to_one_display_configuration(self):
        other = DisplayConfiguration.objects.create(organization_name="Other Org", office_name="Remote Office")
        item = GeneralMessage.objects.create(title="Remote only", message="For remote office", starts_on=date(2026, 1, 1), ends_on=date(2030, 1, 1))
        item.configurations.add(other)
        with patch("signage.services.office_today", return_value=date(2026, 11, 13)):
            self.assertIn("Remote only", [slide["title"] for slide in display_payload(other)["items"]])
            self.assertNotIn("Remote only", [slide["title"] for slide in display_payload(self.config)["items"]])

    def test_display_device_health_and_scoped_feed(self):
        device = DisplayDevice.objects.create(display_id="lobby-tv", name="Lobby TV", configuration=self.config)
        self.assertFalse(device.is_online)
        response = self.client.get(reverse("display_device_public", args=[device.display_id]))
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.is_online)
        feed = self.client.get(reverse("display_device_feed", args=[device.display_id]))
        self.assertEqual(feed.status_code, 200)
        self.assertNotIn("date_of_birth", feed.content.decode())

    def test_staff_backup_contains_database_fixture_and_passes_zip_check(self):
        from .backup import create_backup
        with tempfile.TemporaryDirectory() as folder:
            archive = create_backup(Path(folder) / "test.zip")
            import zipfile
            with zipfile.ZipFile(archive) as zf:
                self.assertIsNone(zf.testzip())
                self.assertIn("database.json", zf.namelist())

    @patch("signage.services.office_today", return_value=date(2026, 11, 13))
    def test_display_uses_category_specific_slide_layouts(self, _today):
        person = Employee.objects.create(employee_id="LAYOUT1", name="Display Person", date_of_birth=date(1990, 11, 13), date_of_joining=date(2021, 11, 13))
        Employee.objects.create(employee_id="LAYOUT2", name="Second Display Person", date_of_birth=date(1992, 11, 13))
        Recognition.objects.create(employee=person, title="Great work", message="Thank you.", starts_on=date(2026, 11, 13), ends_on=date(2026, 11, 13))
        now = timezone.now()
        Announcement.objects.create(title="Notice", description="Important update", starts_at=now-timedelta(minutes=1), ends_at=now+timedelta(hours=1))
        SafetyMessage.objects.create(title="Stay safe", message="Follow the procedure.", starts_on=date(2026, 11, 13), ends_on=date(2026, 11, 13))
        response = self.client.get(reverse("display_birthdays"))
        for category in ("birthday", "anniversary", "recognition", "announcement", "safety"):
            self.assertContains(response, f"slide-{category}")
        self.assertContains(response, "feature-visual")
        self.assertContains(response, "milestone-badge")
        self.assertContains(response, "celebration-variant-1")
        self.assertContains(response, "celebration-variant-2")

class SignageAdminFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="content-operator", password="strong-test-password")
        self.client.force_login(self.user)

    @patch("signage.views.audit", side_effect=RuntimeError("audit storage unavailable"))
    def test_recognition_save_redirects_even_if_audit_logging_fails(self, _audit):
        self.user.user_permissions.add(Permission.objects.get(codename="add_recognition"))
        today = timezone.localdate()
        with self.assertLogs("signage.views", level="ERROR"):
            response = self.client.post(reverse("content_add", args=["recognition"]), {
                "title": "Outstanding work", "message": "Thank you for your contribution.",
                "starts_on": today.isoformat(), "ends_on": today.isoformat(),
                "priority": 50, "is_active": "on",
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Recognition.objects.filter(title="Outstanding work").exists())

    def test_announcement_create_is_permission_controlled_and_audited(self):
        add = Permission.objects.get(codename="add_announcement")
        self.user.user_permissions.add(add)
        start = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        end = start + timedelta(hours=1)
        response = self.client.post(reverse("content_add", args=["announcements"]), {"title": "Team meeting", "description": "Conference room at 2 pm", "starts_at": start.strftime("%Y-%m-%dT%H:%M"), "ends_at": end.strftime("%Y-%m-%dT%H:%M"), "display_duration": 15, "priority": 60, "is_active": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Announcement.objects.filter(title="Team meeting").exists())
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action="create").exists())

    def test_content_edit_page_requires_view_or_change_permission(self):
        response = self.client.get(reverse("content_list", args=["safety"]))
        self.assertEqual(response.status_code, 403)

    def test_system_settings_page_includes_weekly_display_off_controls(self):
        self.user.user_permissions.add(Permission.objects.get(codename="change_contentschedule"))
        response = self.client.get(reverse("system_settings"))
        self.assertContains(response, "Display on schedule")
        self.assertContains(response, 'name="display_off-schedule_enabled"')
        self.assertContains(response, 'name="display_off-monday_start"')

    def test_locomotive_type_can_be_created_and_audited(self):
        permission = Permission.objects.get(codename="add_locomotivetype")
        self.user.user_permissions.add(permission)
        response = self.client.post(reverse("locomotive_type_add"), {"name": "WAG7", "population": 28, "is_active": "on"})
        self.assertEqual(response.status_code, 302)
        locomotive = LocomotiveType.objects.get(name="WAG7")
        self.assertEqual(locomotive.population, 28)
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action="create", target=str(locomotive)).exists())

    def test_full_screen_photo_page_accepts_multiple_uploads_and_displays_them(self):
        from PIL import Image
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_fullscreenphoto"),
            Permission.objects.get(codename="delete_fullscreenphoto"),
            Permission.objects.get(codename="view_fullscreenphoto"),
        )
        image_data = BytesIO()
        Image.new("RGB", (64, 48), "darkgreen").save(image_data, format="JPEG")
        jpeg = image_data.getvalue()
        with tempfile.TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            uploads = {"photos": [
                SimpleUploadedFile("one.jpg", jpeg, content_type="image/jpeg"),
                SimpleUploadedFile("two.jpg", jpeg, content_type="image/jpeg"),
            ]}
            response = self.client.post(reverse("full_screen_photos"), uploads)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(FullScreenPhoto.objects.count(), 2)
            response = self.client.get(reverse("full_screen_photos"))
            self.assertContains(response, "2 photo(s) in the slideshow rotation.")
            photo = FullScreenPhoto.objects.first()
            response = self.client.post(reverse("full_screen_photos"), {"remove_photos": [str(photo.pk)]})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(FullScreenPhoto.objects.count(), 1)

    def test_holiday_calendar_accepts_dates_and_allows_removal(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_displayholiday"),
            Permission.objects.get(codename="delete_displayholiday"),
            Permission.objects.get(codename="view_displayholiday"),
        )
        response = self.client.post(reverse("holiday_calendar"), {
            "name": "Founders Day", "date": "2026-12-01", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        holiday = DisplayHoliday.objects.get(name="Founders Day")
        response = self.client.post(reverse("holiday_calendar"), {"delete_holiday": holiday.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DisplayHoliday.objects.exists())

