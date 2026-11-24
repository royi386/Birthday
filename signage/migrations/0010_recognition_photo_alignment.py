from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("signage", "0009_display_on_schedule")]

    operations = [
        migrations.AddField("recognition", "photo_position_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
        migrations.AddField("recognition", "photo_position_y", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
    ]
