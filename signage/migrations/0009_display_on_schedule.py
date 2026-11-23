from django.db import migrations, models


def preserve_schedule_enablement(apps, schema_editor):
    Schedule = apps.get_model("signage", "DisplayOffSchedule")
    database = schema_editor.connection.alias
    for schedule in Schedule.objects.using(database).all():
        Schedule.objects.using(database).filter(pk=schedule.pk).update(
            schedule_enabled=bool(schedule.enabled),
        )


class Migration(migrations.Migration):
    dependencies = [("signage", "0008_displayoff_weekday_rules")]

    operations = [
        migrations.AddField(
            model_name="displayoffschedule",
            name="schedule_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(preserve_schedule_enablement, migrations.RunPython.noop),
    ]
