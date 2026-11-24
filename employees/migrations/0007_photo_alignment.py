from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("employees", "0006_employeephoto")]

    operations = [
        migrations.AddField("employee", "photo_position_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
        migrations.AddField("employee", "photo_position_y", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
        migrations.AddField("employeephoto", "photo_position_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
        migrations.AddField("employeephoto", "photo_position_y", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
    ]
