import employees.models
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("employees", "0005_employee_display_photo")]

    operations = [
        migrations.CreateModel(
            name="EmployeePhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("photo", models.ImageField(upload_to=employees.models.gallery_photo_path, validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])),
                ("display_photo", models.ImageField(blank=True, editable=False, upload_to=employees.models.gallery_display_photo_path)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gallery_photos", to="employees.employee")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
    ]
