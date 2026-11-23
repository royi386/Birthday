import employees.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("employees", "0004_rename_employee_department_to_section")]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="display_photo",
            field=models.ImageField(blank=True, editable=False, upload_to=employees.models.employee_display_photo_path),
        ),
    ]
