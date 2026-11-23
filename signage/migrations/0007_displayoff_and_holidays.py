import datetime
from django.db import migrations, models


def seed_display_off_schedule(apps, schema_editor):
    Schedule = apps.get_model("signage", "DisplayOffSchedule")
    Schedule.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1,
        defaults={
            "enabled": False,
            "start_time": datetime.time(22, 0),
            "end_time": datetime.time(6, 0),
            "days_of_week": "0,1,2,3,4,5,6",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("signage", "0006_fullscreenphoto")]

    operations = [
        migrations.CreateModel(
            name="DisplayHoliday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("date", models.DateField(db_index=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"ordering": ["date", "name"]},
        ),
        migrations.AddConstraint(
            model_name="displayholiday",
            constraint=models.UniqueConstraint(fields=("name", "date"), name="unique_display_holiday_name_date"),
        ),
        migrations.CreateModel(
            name="DisplayOffSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("start_time", models.TimeField(default=datetime.time(22, 0))),
                ("end_time", models.TimeField(default=datetime.time(6, 0))),
                ("days_of_week", models.CharField(default="0,1,2,3,4,5,6", max_length=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(seed_display_off_schedule, migrations.RunPython.noop),
    ]
