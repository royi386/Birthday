from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("employees", "0001_initial")]
    operations = [migrations.CreateModel(name="DisplayConfiguration", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("office_name", models.CharField(default="Your Office", max_length=140)), ("birthday_greeting", models.CharField(default="Many many happy returns of the day!", max_length=240)), ("slide_duration", models.PositiveSmallIntegerField(default=10)), ("theme", models.CharField(choices=[("professional", "Professional Blue & Gold"), ("celebration", "Elegant Celebration"), ("minimal", "Minimal Corporate")], default="professional", max_length=20)), ("updated_at", models.DateTimeField(auto_now=True))], options={"verbose_name": "display configuration", "permissions": [("manage_displayconfiguration", "Can manage display configuration")]})]
