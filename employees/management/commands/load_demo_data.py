from datetime import date, timedelta
from django.core.management.base import BaseCommand
from employees.models import Employee
from signage.services import office_today


class Command(BaseCommand):
    help = "Create three clearly labeled fictitious employees for testing, including one birthday today."

    def handle(self, *args, **options):
        today = office_today()
        samples = [
            ("DEMO-TODAY", "Demo Birthday Employee", date(1990, today.month, today.day)),
            ("DEMO-TOMORROW", "Demo Upcoming Employee", date(1992, (today + timedelta(days=1)).month, (today + timedelta(days=1)).day)),
            ("DEMO-LEAP", "Demo Leap Day Employee", date(1988, 2, 29)),
        ]
        for employee_id, name, birthday in samples:
            employee, created = Employee.objects.update_or_create(
                employee_id=employee_id,
                defaults={
                    "name": name,
                    "designation": "Sample record",
                    "section": "Demonstration",
                    "date_of_birth": birthday,
                    "date_of_joining": None,
                    "is_active": True,
                },
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} {employee.employee_id}: {employee.name}")
        self.stdout.write(self.style.SUCCESS("Demo employees are ready. Remove DEMO-* records before production."))

