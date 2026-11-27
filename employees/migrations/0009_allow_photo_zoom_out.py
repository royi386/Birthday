from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("employees", "0008_photo_zoom")]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="photo_zoom",
            field=models.PositiveSmallIntegerField(
                default=160,
                validators=[django.core.validators.MinValueValidator(25), django.core.validators.MaxValueValidator(300)],
            ),
        ),
        migrations.AlterField(
            model_name="employeephoto",
            name="photo_zoom",
            field=models.PositiveSmallIntegerField(
                default=160,
                validators=[django.core.validators.MinValueValidator(25), django.core.validators.MaxValueValidator(300)],
            ),
        ),
    ]
