from django import forms
from employees.forms import validate_image_upload
from .models import Announcement, DisplayDevice, DisplayHoliday, DisplayOffSchedule, FullScreenPhoto, GeneralMessage, LocomotiveType, Recognition, SafetyMessage, ContentSchedule

class ImageValidationMixin:
    def clean(self):
        cleaned = super().clean()
        for name in ("photo", "image"):
            uploaded = cleaned.get(name)
            if uploaded and hasattr(uploaded, "size"):
                try: validate_image_upload(uploaded)
                except forms.ValidationError as exc: self.add_error(name, exc)
        return cleaned

class RecognitionForm(ImageValidationMixin, forms.ModelForm):
    class Meta:
        model = Recognition
        fields = ["employee", "title", "message", "photo", "starts_on", "ends_on", "priority", "is_active", "configurations"]
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}), "ends_on": forms.DateInput(attrs={"type": "date"}), "message": forms.Textarea(attrs={"rows": 4})}

class AnnouncementForm(ImageValidationMixin, forms.ModelForm):
    display_duration = forms.IntegerField(min_value=1, max_value=28800, required=False, help_text="Seconds on screen; leave blank to use the category setting.", widget=forms.NumberInput(attrs={"min": 1, "max": 28800}))
    class Meta:
        model = Announcement
        fields = ["title", "description", "image", "starts_at", "ends_at", "display_duration", "priority", "is_active", "configurations"]
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), "description": forms.Textarea(attrs={"rows": 4})}
        input_formats = {"starts_at": ["%Y-%m-%dT%H:%M"], "ends_at": ["%Y-%m-%dT%H:%M"]}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ("starts_at", "ends_at"):
            self.fields[field].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S%z"]

class SafetyMessageForm(ImageValidationMixin, forms.ModelForm):
    display_duration = forms.IntegerField(min_value=1, max_value=28800, required=False, help_text="Seconds on screen; leave blank to use the category setting.", widget=forms.NumberInput(attrs={"min": 1, "max": 28800}))
    class Meta:
        model = SafetyMessage
        fields = ["title", "message", "image", "category", "starts_on", "ends_on", "display_duration", "priority", "is_active", "configurations"]
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}), "ends_on": forms.DateInput(attrs={"type": "date"}), "message": forms.Textarea(attrs={"rows": 4})}

class GeneralMessageForm(ImageValidationMixin, forms.ModelForm):
    display_duration = forms.IntegerField(min_value=1, max_value=28800, required=False, help_text="Seconds on screen; leave blank to use the category setting.", widget=forms.NumberInput(attrs={"min": 1, "max": 28800}))
    class Meta:
        model = GeneralMessage
        fields = ["title", "message", "image", "starts_on", "ends_on", "display_duration", "priority", "is_active", "configurations"]
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}), "ends_on": forms.DateInput(attrs={"type": "date"}), "message": forms.Textarea(attrs={"rows": 4})}

class DisplayDeviceForm(forms.ModelForm):
    class Meta:
        model = DisplayDevice
        fields = ["display_id", "name", "configuration", "is_enabled"]

class ContentScheduleForm(forms.ModelForm):
    duration = forms.IntegerField(min_value=1, max_value=28800, widget=forms.NumberInput(attrs={"min": 1, "max": 28800}))
    class Meta:
        model = ContentSchedule
        fields = ["enabled", "priority", "duration"]
        widgets = {"priority": forms.NumberInput(attrs={"min": 1, "max": 100}), "duration": forms.NumberInput(attrs={"min": 1, "max": 28800})}

class LocomotiveTypeForm(ImageValidationMixin, forms.ModelForm):
    class Meta:
        model = LocomotiveType
        fields = ["name", "photo", "population", "is_active"]
        widgets = {"population": forms.NumberInput(attrs={"min": 0})}

class MultiplePhotoInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultiplePhotoField(forms.FileField):
    widget = MultiplePhotoInput

    def clean(self, data, initial=None):
        if not data:
            return []
        uploads = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultiplePhotoField, self).clean(upload, initial) for upload in uploads]

class FullScreenPhotoForm(forms.Form):
    photos = MultiplePhotoField(
        required=False,
        label="Upload photos",
        help_text="Select multiple JPEG, PNG or WebP images. Each file can be up to 10 MB.",
        widget=MultiplePhotoInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remove_photos = forms.MultipleChoiceField(required=False, choices=(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["remove_photos"].choices = [
            (str(photo.pk), photo.photo.name.rsplit("/", 1)[-1])
            for photo in FullScreenPhoto.objects.all()
        ]

    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        for photo in photos:
            validate_image_upload(photo, label="Photo")
        return photos

class DisplayOffScheduleForm(forms.Form):
    WEEKDAY_FIELDS = [
        ("monday", "Monday", "0"), ("tuesday", "Tuesday", "1"),
        ("wednesday", "Wednesday", "2"), ("thursday", "Thursday", "3"),
        ("friday", "Friday", "4"), ("saturday", "Saturday", "5"),
        ("sunday", "Sunday", "6"),
    ]

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance", None) or DisplayOffSchedule()
        super().__init__(*args, **kwargs)
        rules = self.instance.weekday_rules or {}
        for key, label, day in self.WEEKDAY_FIELDS:
            rule = rules.get(day, {})
            self.fields[f"{key}_enabled"] = forms.BooleanField(required=False, label=label)
            self.fields[f"{key}_start"] = forms.TimeField(
                required=False, label="From", widget=forms.TimeInput(attrs={"type": "time"}),
            )
            self.fields[f"{key}_end"] = forms.TimeField(
                required=False, label="To", widget=forms.TimeInput(attrs={"type": "time"}),
            )
            self.initial[f"{key}_enabled"] = bool(rule.get("enabled", False))
            self.initial[f"{key}_start"] = rule.get("start", "22:00")
            self.initial[f"{key}_end"] = rule.get("end", "06:00")

    def clean(self):
        cleaned = super().clean()
        for key, label, _day in self.WEEKDAY_FIELDS:
            if not cleaned.get(f"{key}_enabled"):
                continue
            start = cleaned.get(f"{key}_start")
            end = cleaned.get(f"{key}_end")
            if not start:
                self.add_error(f"{key}_start", f"Choose a start time for {label}.")
            if not end:
                self.add_error(f"{key}_end", f"Choose an end time for {label}.")
            if start and end and start == end:
                self.add_error(f"{key}_end", "Start and end times must be different.")
        return cleaned

    def save(self, commit=True):
        rules = {}
        for key, _label, day in self.WEEKDAY_FIELDS:
            start = self.cleaned_data.get(f"{key}_start")
            end = self.cleaned_data.get(f"{key}_end")
            rules[day] = {
                "enabled": bool(self.cleaned_data.get(f"{key}_enabled")),
                "start": start.strftime("%H:%M") if start else "22:00",
                "end": end.strftime("%H:%M") if end else "06:00",
            }
        self.instance.weekday_rules = rules
        if commit:
            self.instance.save()
        return self.instance

class DisplayHolidayForm(forms.ModelForm):
    class Meta:
        model = DisplayHoliday
        fields = ["name", "date", "is_active"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
