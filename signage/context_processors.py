from employees.models import DisplayConfiguration


def display_identity(request):
    config = DisplayConfiguration.objects.first()
    if config is None:
        return {"site_organization": "Office Digital Display", "site_office": "Your Office", "site_logo": ""}
    try:
        logo = config.logo.url if config.logo else ""
    except (ValueError, OSError):
        logo = ""
    return {"site_organization": config.organization_name, "site_office": config.office_name, "site_logo": logo}
