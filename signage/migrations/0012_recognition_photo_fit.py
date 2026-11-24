from django.db import migrations, models
import django.core.validators


def reset_default_zoom(apps, schema_editor):
    Recognition = apps.get_model("signage", "Recognition")
    Recognition.objects.filter(photo_zoom=160).update(photo_zoom=100)


class Migration(migrations.Migration):
    dependencies = [("signage", "0011_recognition_photo_zoom")]

    operations = [
        migrations.RunPython(reset_default_zoom, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="recognition",
            name="photo_zoom",
            field=models.PositiveSmallIntegerField(
                default=100,
                validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(300)],
            ),
        ),
    ]
