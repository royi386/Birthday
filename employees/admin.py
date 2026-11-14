from django.contrib import admin
from .models import DisplayConfiguration, Employee
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "name", "section", "designation", "is_active")
    list_filter = ("is_active", "section")
    search_fields = ("employee_id", "name", "section")

@admin.register(DisplayConfiguration)
class DisplayConfigurationAdmin(admin.ModelAdmin):
    list_display = ("office_name", "theme", "slide_duration", "updated_at")
    def has_add_permission(self, request):
        return not DisplayConfiguration.objects.exists() and super().has_add_permission(request)
