from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("signage", "0004_locomotivetype_alter_contentschedule_category")]

    operations = [
        migrations.AlterField(
            model_name="contentschedule", name="duration",
            field=models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(1), MaxValueValidator(28800)]),
        ),
        migrations.AlterField(
            model_name="announcement", name="display_duration",
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[MinValueValidator(1), MaxValueValidator(28800)]),
        ),
        migrations.AlterField(
            model_name="safetymessage", name="display_duration",
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[MinValueValidator(1), MaxValueValidator(28800)]),
        ),
        migrations.AlterField(
            model_name="generalmessage", name="display_duration",
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[MinValueValidator(1), MaxValueValidator(28800)]),
        ),
    ]
