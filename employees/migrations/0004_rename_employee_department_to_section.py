from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0003_displayconfiguration_anniversary_milestones_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="employee",
            old_name="department",
            new_name="section",
        ),
    ]
