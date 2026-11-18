from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial admin account if it does not already exist."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        if created:
            user.set_password("admin")
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Created initial superuser 'admin'."))
        else:
            self.stdout.write("Initial admin account already exists; its credentials were left unchanged.")
