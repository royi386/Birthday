from django import forms
from django.utils import timezone
from .models import DisplayConfiguration, Employee

MAX_IMAGE_UPLOAD_SIZE = 10 * 1024 * 1024

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["employee_id", "name", "designation", "section", "date_of_birth", "photo", "date_of_joining", "is_active"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"}), "date_of_joining": forms.DateInput(attrs={"type": "date"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].help_text = "JPEG, PNG or WebP image, up to 10 MB."
    def clean_employee_id(self): return self.cleaned_data["employee_id"].strip()

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean_date_of_joining(self):
        joined = self.cleaned_data.get("date_of_joining")
        if joined and joined > timezone.localdate():
            raise forms.ValidationError("Date of joining cannot be in the future.")
        return joined

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        validate_image_upload(photo, label="Photo")
        return photo

class DisplayConfigurationForm(forms.ModelForm):
    milestones = forms.MultipleChoiceField(choices=[(str(n), f"{n} years") for n in (1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)], required=False, widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = DisplayConfiguration
        fields = ["organization_name", "office_name", "logo", "background_image", "birthday_greeting", "slide_duration", "theme", "transition", "timezone_name", "date_format", "refresh_interval", "empty_title", "empty_message", "leap_day_policy"]
        widgets = {"birthday_greeting": forms.TextInput(attrs={"maxlength": 240}), "slide_duration": forms.NumberInput(attrs={"min": 5, "max": 30}), "timezone_name": forms.TextInput(attrs={"placeholder": "Asia/Kolkata"}), "refresh_interval": forms.NumberInput(attrs={"min": 10, "max": 300})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = self.instance.anniversary_milestones if self.instance and self.instance.pk else "1,5,10,15,20,25,30"
        self.fields["milestones"].initial = [value.strip() for value in raw.split(",") if value.strip()]

    def clean_milestones(self):
        return ",".join(sorted(set(self.cleaned_data["milestones"]), key=int))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.anniversary_milestones = self.cleaned_data["milestones"]
        if commit: instance.save()
        return instance

    def clean(self):
        cleaned = super().clean()
        for field_name in ("logo", "background_image"):
            uploaded = cleaned.get(field_name)
            if uploaded and hasattr(uploaded, "size"):
                try: validate_image_upload(uploaded)
                except forms.ValidationError as exc: self.add_error(field_name, exc)
        return cleaned

def validate_image_upload(uploaded, label="Image"):
    from PIL import Image, UnidentifiedImageError
    if uploaded.size > MAX_IMAGE_UPLOAD_SIZE:
        raise forms.ValidationError(f"{label} must be 10 MB or smaller.")
    try:
        image = Image.open(uploaded)
        image_format = image.format
        if image_format not in ("JPEG", "MPO", "PNG", "WEBP"):
            raise forms.ValidationError(f"Unsupported image format ({image_format or 'unknown'}). Use a JPEG, PNG or WebP image.")
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError("The uploaded file is not a valid image.")
    uploaded.seek(0)

