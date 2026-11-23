from django import forms
from employees.forms import validate_image_upload
from .models import Announcement, DisplayDevice, FullScreenPhoto, GeneralMessage, LocomotiveType, Recognition, SafetyMessage, ContentSchedule

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
