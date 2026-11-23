import django.core.validators
from django.db import migrations, models


def seed_photos_schedule(apps, schema_editor):
    ContentSchedule = apps.get_model("signage", "ContentSchedule")
    ContentSchedule.objects.using(schema_editor.connection.alias).get_or_create(
        category="photos",
        defaults={"enabled": True, "priority": 50, "duration": 10},
    )


class Migration(migrations.Migration):
    dependencies = [("signage", "0005_duration_range")]

    operations = [
        migrations.CreateModel(
            name="FullScreenPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("photo", models.ImageField(upload_to="full_screen_photos/", validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["uploaded_at", "pk"]},
        ),
        migrations.AlterField(
            model_name="contentschedule",
            name="category",
            field=models.CharField(choices=[
                ("birthday", "Birthday wishes"), ("anniversary", "Work anniversaries"),
                ("recognition", "Employee recognition"), ("announcement", "Office announcements"),
                ("safety", "Safety messages"), ("general", "General information"),
                ("photos", "Full screen photos"), ("fleet", "Locomotive population"),
            ], max_length=20, unique=True),
        ),
        migrations.RunPython(seed_photos_schedule, migrations.RunPython.noop),
    ]
