from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("signage", "0012_recognition_photo_fit")]

    operations = [
        migrations.AlterField(
            model_name="recognition",
            name="photo_zoom",
            field=models.PositiveSmallIntegerField(
                default=100,
                validators=[django.core.validators.MinValueValidator(25), django.core.validators.MaxValueValidator(300)],
            ),
        ),
    ]
