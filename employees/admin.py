from django.contrib import admin
from .models import DisplayConfiguration, Employee, EmployeePhoto

class EmployeePhotoInline(admin.TabularInline):
    model = EmployeePhoto
    extra = 1
    fields = ("photo", "display_photo", "created_at")
    readonly_fields = ("display_photo", "created_at")

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "name", "section", "designation", "is_active")
    list_filter = ("is_active", "section")
    search_fields = ("employee_id", "name", "section")
    inlines = (EmployeePhotoInline,)

@admin.register(DisplayConfiguration)
class DisplayConfigurationAdmin(admin.ModelAdmin):
    list_display = ("office_name", "theme", "slide_duration", "updated_at")
    def has_add_permission(self, request):
        return not DisplayConfiguration.objects.exists() and super().has_add_permission(request)
