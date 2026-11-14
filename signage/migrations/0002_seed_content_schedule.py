from django.db import migrations

DEFAULTS = [("birthday", True, 100, 10), ("anniversary", True, 90, 10), ("safety", True, 85, 15), ("recognition", True, 70, 15), ("announcement", True, 60, 15), ("general", True, 40, 15)]

def seed_schedules(apps, schema_editor):
    Schedule = apps.get_model("signage", "ContentSchedule")
    for category, enabled, priority, duration in DEFAULTS:
        Schedule.objects.using(schema_editor.connection.alias).get_or_create(category=category, defaults={"enabled": enabled, "priority": priority, "duration": duration})

class Migration(migrations.Migration):
    dependencies = [("signage", "0001_initial")]
    operations = [migrations.RunPython(seed_schedules, migrations.RunPython.noop)]
