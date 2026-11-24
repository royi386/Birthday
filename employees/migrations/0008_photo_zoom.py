from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("employees", "0007_photo_alignment")]

    operations = [
        migrations.AddField("employee", "photo_zoom", models.PositiveSmallIntegerField(default=160, validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(300)])),
        migrations.AddField("employeephoto", "photo_zoom", models.PositiveSmallIntegerField(default=160, validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(300)])),
    ]
