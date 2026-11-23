from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q

from employees.models import Employee
from employees.photo_processing import centered_face_jpeg


class Command(BaseCommand):
    help = "Create face-centered display crops for employee photos that do not have one yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate display crops that already exist.",
        )

    def handle(self, *args, **options):
        processed = no_face = failed = 0
        employees = Employee.objects.exclude(photo="")
        if not options["force"]:
            employees = employees.filter(
                Q(display_photo="")
                | ~Q(display_photo__endswith="-centered-v2.jpg")
            )
        employees = employees.iterator()
        for employee in employees:
            try:
                with employee.photo.open("rb") as photo:
                    centered = centered_face_jpeg(photo)
                if not centered:
                    no_face += 1
                    if employee.display_photo:
                        employee.display_photo.delete(save=False)
                        employee.save(update_fields=["display_photo"])
                    continue
                filename = f"{Path(employee.photo.name).stem}-centered-v2.jpg"
                if employee.display_photo:
                    employee.display_photo.delete(save=False)
                employee.display_photo.save(filename, ContentFile(centered), save=False)
                employee.save(update_fields=["display_photo"])
                processed += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Could not process employee {employee.employee_id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Created centered crops for {processed} employee photos; "
                f"no face detected in {no_face}; failed {failed}."
            )
        )
