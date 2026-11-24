from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("signage", "0010_recognition_photo_alignment")]

    operations = [
        migrations.AddField("recognition", "photo_zoom", models.PositiveSmallIntegerField(default=160, validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(300)])),
    ]
