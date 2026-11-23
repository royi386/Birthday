from django.contrib import admin
from .models import Announcement, AuditLog, ContentSchedule, DisplayDevice, FullScreenPhoto, GeneralMessage, LocomotiveType, Recognition, SafetyMessage

@admin.register(ContentSchedule)
class ContentScheduleAdmin(admin.ModelAdmin):
    list_display = ("category", "enabled", "priority", "duration")
    list_editable = ("enabled", "priority", "duration")

@admin.register(Recognition)
class RecognitionAdmin(admin.ModelAdmin):
    list_display = ("title", "employee", "starts_on", "ends_on", "priority", "is_active")
    list_filter = ("is_active", "starts_on", "ends_on")
    search_fields = ("title", "employee__name", "message")

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "ends_at", "priority", "is_active")
    list_filter = ("is_active", "starts_at", "ends_at")
    search_fields = ("title", "description")

@admin.register(SafetyMessage)
class SafetyMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "starts_on", "ends_on", "priority", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("title", "message")

@admin.register(GeneralMessage)
class GeneralMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_on", "ends_on", "priority", "is_active")
    list_filter = ("is_active", "starts_on", "ends_on")
    search_fields = ("title", "message")

@admin.register(LocomotiveType)
class LocomotiveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "population", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(FullScreenPhoto)
class FullScreenPhotoAdmin(admin.ModelAdmin):
    list_display = ("photo", "uploaded_at")
    readonly_fields = ("uploaded_at",)

@admin.register(DisplayDevice)
class DisplayDeviceAdmin(admin.ModelAdmin):
    list_display = ("display_id", "name", "configuration", "is_enabled", "last_seen")
    list_filter = ("is_enabled",)
    readonly_fields = ("registration_token", "last_seen", "created_at")

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("summary", "target", "actor__username")
    readonly_fields = ("actor", "action", "target", "summary", "created_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
