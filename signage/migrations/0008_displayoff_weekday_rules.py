from django.db import migrations, models


def copy_legacy_schedule(apps, schema_editor):
    Schedule = apps.get_model("signage", "DisplayOffSchedule")
    database = schema_editor.connection.alias
    for schedule in Schedule.objects.using(database).all():
        try:
            enabled_days = {day for day in schedule.days_of_week.split(",") if day}
        except AttributeError:
            enabled_days = set()
        rules = {
            str(day): {
                "enabled": bool(schedule.enabled and str(day) in enabled_days),
                "start": schedule.start_time.strftime("%H:%M"),
                "end": schedule.end_time.strftime("%H:%M"),
            }
            for day in range(7)
        }
        Schedule.objects.using(database).filter(pk=schedule.pk).update(weekday_rules=rules)


class Migration(migrations.Migration):
    dependencies = [("signage", "0007_displayoff_and_holidays")]

    operations = [
        migrations.AddField(
            model_name="displayoffschedule",
            name="weekday_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copy_legacy_schedule, migrations.RunPython.noop),
    ]
