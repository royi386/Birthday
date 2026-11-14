import uuid
from datetime import timedelta
from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

IMAGE_VALIDATOR = FileExtensionValidator(["jpg", "jpeg", "png", "webp"])

class ContentSchedule(models.Model):
    CATEGORY_CHOICES = [("birthday", "Birthday wishes"), ("anniversary", "Work anniversaries"), ("recognition", "Employee recognition"), ("announcement", "Office announcements"), ("safety", "Safety messages"), ("general", "General information"), ("fleet", "Locomotive population")]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(1), MaxValueValidator(100)])
    duration = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(5), MaxValueValidator(30)])
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-priority", "category"]
    def __str__(self): return self.get_category_display()

class Recognition(models.Model):
    employee = models.ForeignKey("employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="recognitions")
    title = models.CharField(max_length=180)
    message = models.TextField(max_length=1600)
    photo = models.ImageField(upload_to="recognition/", blank=True, validators=[IMAGE_VALIDATOR])
    starts_on = models.DateField(db_index=True)
    ends_on = models.DateField(db_index=True)
    priority = models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(1), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True, db_index=True)
    configurations = models.ManyToManyField("employees.DisplayConfiguration", blank=True, related_name="recognitions")
    created_at = models.DateTimeField(auto_now_add=True)
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on: raise ValidationError({"ends_on": "End date must be on or after the start date."})
    def __str__(self): return self.title

class Announcement(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=2400)
    image = models.ImageField(upload_to="announcements/", blank=True, validators=[IMAGE_VALIDATOR])
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    display_duration = models.PositiveSmallIntegerField(null=True, blank=True, default=None, validators=[MinValueValidator(5), MaxValueValidator(30)])
    priority = models.PositiveSmallIntegerField(default=50, validators=[MinValueValidator(1), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True, db_index=True)
    configurations = models.ManyToManyField("employees.DisplayConfiguration", blank=True, related_name="announcements")
    created_at = models.DateTimeField(auto_now_add=True)
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at: raise ValidationError({"ends_at": "End time must be later than start time."})
    def __str__(self): return self.title

class SafetyMessage(models.Model):
    CATEGORY_CHOICES = [("general", "General safety"), ("fire", "Fire safety"), ("electrical", "Electrical safety"), ("workplace", "Workplace safety"), ("emergency", "Emergency procedure"), ("wellbeing", "Health and wellbeing")]
    title = models.CharField(max_length=180)
    message = models.TextField(max_length=1600)
    image = models.ImageField(upload_to="safety/", blank=True, validators=[IMAGE_VALIDATOR])
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    starts_on = models.DateField(db_index=True)
    ends_on = models.DateField(db_index=True)
    display_duration = models.PositiveSmallIntegerField(null=True, blank=True, default=None, validators=[MinValueValidator(5), MaxValueValidator(30)])
    priority = models.PositiveSmallIntegerField(default=75, validators=[MinValueValidator(1), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True, db_index=True)
    configurations = models.ManyToManyField("employees.DisplayConfiguration", blank=True, related_name="safety_messages")
    created_at = models.DateTimeField(auto_now_add=True)
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on: raise ValidationError({"ends_on": "End date must be on or after the start date."})
    def __str__(self): return self.title

class GeneralMessage(models.Model):
    title = models.CharField(max_length=180)
    message = models.TextField(max_length=1600)
    image = models.ImageField(upload_to="general/", blank=True, validators=[IMAGE_VALIDATOR])
    starts_on = models.DateField(db_index=True)
    ends_on = models.DateField(db_index=True)
    display_duration = models.PositiveSmallIntegerField(null=True, blank=True, default=None, validators=[MinValueValidator(5), MaxValueValidator(30)])
    priority = models.PositiveSmallIntegerField(default=40, validators=[MinValueValidator(1), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True, db_index=True)
    configurations = models.ManyToManyField("employees.DisplayConfiguration", blank=True, related_name="general_messages")
    created_at = models.DateTimeField(auto_now_add=True)
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on: raise ValidationError({"ends_on": "End date must be on or after the start date."})
    def __str__(self): return self.title

class LocomotiveType(models.Model):
    name = models.CharField(max_length=60, unique=True)
    photo = models.ImageField(upload_to="locomotives/", blank=True, validators=[IMAGE_VALIDATOR])
    population = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["name"]
        verbose_name = "locomotive type"
        verbose_name_plural = "locomotive population"
    def __str__(self): return f"{self.name} ({self.population})"

class DisplayDevice(models.Model):
    display_id = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=120)
    registration_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    configuration = models.ForeignKey("employees.DisplayConfiguration", null=True, blank=True, on_delete=models.SET_NULL, related_name="devices")
    is_enabled = models.BooleanField(default=True, db_index=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def mark_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=["last_seen"])
    @property
    def is_online(self): return bool(self.last_seen and self.last_seen >= timezone.now() - timedelta(minutes=3))
    @property
    def display_url(self): return f"/display/device/{self.display_id}/"
    def __str__(self): return f"{self.name} ({self.display_id})"

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="signage_audit_entries")
    action = models.CharField(max_length=50, db_index=True)
    target = models.CharField(max_length=180, blank=True)
    summary = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self): return f"{self.action}: {self.summary}"
