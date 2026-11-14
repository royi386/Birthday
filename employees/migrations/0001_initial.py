from django.db import migrations, models
import django.core.validators
import employees.models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="Employee", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("employee_id", models.CharField(db_index=True, max_length=40, unique=True)), ("name", models.CharField(max_length=160)), ("designation", models.CharField(blank=True, max_length=120)), ("department", models.CharField(blank=True, db_index=True, max_length=120)), ("date_of_birth", models.DateField()), ("photo", models.ImageField(blank=True, upload_to=employees.models.employee_photo_path, validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])), ("date_of_joining", models.DateField(blank=True, null=True)), ("is_active", models.BooleanField(db_index=True, default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True))], options={"ordering": ["name", "employee_id"], "indexes": [models.Index(fields=["is_active", "date_of_birth"], name="employees_e_is_acti_e17761_idx")]})]
