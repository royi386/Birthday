import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from employees.models import DisplayConfiguration, Employee
from .models import Announcement, AuditLog, ContentSchedule, DisplayDevice, GeneralMessage, LocomotiveType, Recognition, SafetyMessage
from .services import build_display_items, display_payload, upcoming_anniversaries

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

    @patch("signage.services.office_today", return_value=date(2026, 3, 1))
    def test_leap_day_policy_can_shift_birthday_to_march_first(self, _today):
        self.config.leap_day_policy = "mar1"; self.config.save()
        Employee.objects.create(employee_id="LEAP1", name="Leap Employee", date_of_birth=date(2000, 2, 29))
        items = build_display_items(self.config)
        self.assertEqual([item["name"] for item in items if item["category"] == "birthday"], ["Leap Employee"])

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
    def test_locomotive_population_is_daily_and_lowest_priority(self, _today):
        ContentSchedule.objects.filter(category="fleet").update(priority=1, duration=12)
        LocomotiveType.objects.create(name="WAP5", population=11)
        LocomotiveType.objects.create(name="WAP7", population=43)
        GeneralMessage.objects.create(title="Office hours", message="Open at nine", starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 30))
        slides = build_display_items(self.config)
        fleet = [item for item in slides if item["category"] == "fleet"]
        self.assertEqual([item["title"] for item in fleet], ["WAP5", "WAP7"])
        self.assertEqual([item["message"] for item in fleet], ["Present population: 11", "Present population: 43"])
        self.assertTrue(all(item["duration"] == 12 for item in fleet))
        self.assertEqual(slides[-1]["category"], "fleet")
        self.assertEqual(ContentSchedule.objects.get(category="fleet").priority, 1)

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

class SignageAdminFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="content-operator", password="strong-test-password")
        self.client.force_login(self.user)

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

    def test_locomotive_type_can_be_created_and_audited(self):
        permission = Permission.objects.get(codename="add_locomotivetype")
        self.user.user_permissions.add(permission)
        response = self.client.post(reverse("locomotive_type_add"), {"name": "WAG7", "population": 28, "is_active": "on"})
        self.assertEqual(response.status_code, 302)
        locomotive = LocomotiveType.objects.get(name="WAG7")
        self.assertEqual(locomotive.population, 28)
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action="create", target=str(locomotive)).exists())

