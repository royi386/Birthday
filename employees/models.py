from django.core.validators import FileExtensionValidator
from django.db import models
from pathlib import Path

def employee_photo_path(instance, filename):
    return f"employees/{instance.employee_id}/{filename}"

def employee_display_photo_path(instance, filename):
    return f"employees/{instance.employee_id}/display/{Path(filename).name}"

def gallery_photo_path(instance, filename):
    return f"employees/{instance.employee.employee_id}/gallery/{Path(filename).name}"

def gallery_display_photo_path(instance, filename):
    return f"employees/{instance.employee.employee_id}/gallery/display/{Path(filename).name}"

class Employee(models.Model):
    employee_id = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=160)
    designation = models.CharField(max_length=120, blank=True)
    section = models.CharField(max_length=120, blank=True, db_index=True)
    date_of_birth = models.DateField()
    photo = models.ImageField(upload_to=employee_photo_path, blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    display_photo = models.ImageField(upload_to=employee_display_photo_path, blank=True, editable=False)
    date_of_joining = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["name", "employee_id"]
        indexes = [models.Index(fields=["is_active", "date_of_birth"])]
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        photo_is_being_saved = update_fields is None or "photo" in update_fields
        uploaded_photo = getattr(self.photo, "_file", None) if self.photo else None
        if photo_is_being_saved and uploaded_photo is not None:
            from django.core.files.base import ContentFile
            from .photo_processing import centered_face_jpeg
            centered = centered_face_jpeg(uploaded_photo)
            if centered:
                filename = f"{Path(self.photo.name).stem}-centered-v2.jpg"
                self.display_photo.save(filename, ContentFile(centered), save=False)
            elif self.display_photo:
                self.display_photo.delete(save=False)
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"display_photo"}
        elif photo_is_being_saved and not self.photo and self.display_photo:
            self.display_photo.delete(save=False)
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"display_photo"}
        super().save(*args, **kwargs)
    def __str__(self): return f"{self.name} ({self.employee_id})"

class EmployeePhoto(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="gallery_photos")
    photo = models.ImageField(upload_to=gallery_photo_path, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    display_photo = models.ImageField(upload_to=gallery_display_photo_path, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def save(self, *args, **kwargs):
        uploaded_photo = getattr(self.photo, "_file", None) if self.photo else None
        if uploaded_photo is not None:
            from django.core.files.base import ContentFile
            from .photo_processing import centered_face_jpeg
            centered = centered_face_jpeg(uploaded_photo)
            if centered:
                filename = f"{Path(self.photo.name).stem}-centered-v2.jpg"
                self.display_photo.save(filename, ContentFile(centered), save=False)
        super().save(*args, **kwargs)

    def __str__(self): return f"Photo of {self.employee}"

class DisplayConfiguration(models.Model):
    THEME_CHOICES = [("professional", "Professional Blue & Gold"), ("celebration", "Elegant Celebration"), ("minimal", "Minimal Corporate")]
    LEAP_DAY_CHOICES = [("feb28", "Show on 28 February"), ("mar1", "Show on 1 March")]
    TRANSITION_CHOICES = [("fade", "Fade"), ("slide", "Slide")]
    DATE_FORMAT_CHOICES = [("weekday", "Weekday, day month year"), ("short", "DD/MM/YYYY"), ("long", "Month day, year")]
    organization_name = models.CharField(max_length=140, default="Office Digital Display")
    office_name = models.CharField(max_length=140, default="Your Office")
    logo = models.ImageField(upload_to="branding/", blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    background_image = models.ImageField(upload_to="branding/", blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    birthday_greeting = models.CharField(max_length=240, default="Many many happy returns of the day!")
    slide_duration = models.PositiveSmallIntegerField(default=10)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default="professional")
    transition = models.CharField(max_length=12, choices=TRANSITION_CHOICES, default="fade")
    timezone_name = models.CharField(max_length=64, default="Asia/Kolkata")
    date_format = models.CharField(max_length=12, choices=DATE_FORMAT_CHOICES, default="weekday")
    refresh_interval = models.PositiveSmallIntegerField(default=60)
    empty_title = models.CharField(max_length=140, default="Good things happen together.")
    empty_message = models.CharField(max_length=240, default="Wishing everyone a wonderful day.")
    leap_day_policy = models.CharField(max_length=8, choices=LEAP_DAY_CHOICES, default="feb28")
    anniversary_milestones = models.CharField(max_length=120, default="1,5,10,15,20,25,30")
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "display configuration"
        permissions = [("manage_displayconfiguration", "Can manage display configuration")]
    def clean(self):
        from django.core.exceptions import ValidationError
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError): raise ValidationError({"timezone_name": "Enter a valid IANA timezone, such as Asia/Kolkata."})
        if not 1 <= self.slide_duration <= 28800:
            raise ValidationError({"slide_duration": "Duration must be between 1 second and 8 hours."})
        if not 10 <= self.refresh_interval <= 300:
            raise ValidationError({"refresh_interval": "Refresh interval must be between 10 and 300 seconds."})
        try: milestones = [int(value) for value in self.anniversary_milestones.split(",") if value.strip()]
        except ValueError: raise ValidationError({"anniversary_milestones": "Use comma-separated positive year milestones."})
        if any(value < 1 or value > 50 for value in milestones): raise ValidationError({"anniversary_milestones": "Milestones must be from 1 to 50 years."})
    def __str__(self): return "Birthday display configuration"
