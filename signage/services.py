from datetime import date, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Q
from django.utils import timezone
from employees.models import DisplayConfiguration, Employee
from .models import Announcement, ContentSchedule, GeneralMessage, LocomotiveType, Recognition, SafetyMessage

DEFAULT_SCHEDULE = {
    "birthday": (True, 100, 10), "anniversary": (True, 90, 10),
    "safety": (True, 85, 15), "recognition": (True, 70, 15),
    "announcement": (True, 60, 15), "general": (True, 40, 15), "fleet": (True, 1, 10),
}

def office_today(config=None):
    config = config or DisplayConfiguration.objects.first()
    zone = ZoneInfo(config.timezone_name) if config else ZoneInfo("Asia/Kolkata")
    return timezone.localdate(timezone.now(), zone)

def display_config(device=None):
    if device and device.configuration_id:
        return device.configuration
    return DisplayConfiguration.objects.first()

def enabled_schedules():
    stored = {item.category: item for item in ContentSchedule.objects.all()}
    result = {}
    for category, (enabled, priority, duration) in DEFAULT_SCHEDULE.items():
        result[category] = stored.get(category) or type("ScheduleDefault", (), {"category": category, "enabled": enabled, "priority": priority, "duration": duration})()
    return result

def _is_configured_for(queryset, relation, config):
    if config is None:
        return queryset.filter(**{f"{relation}__isnull": True})
    return queryset.filter(Q(**{f"{relation}__isnull": True}) | Q(**{relation: config})).distinct()

def _image(field):
    try: return field.url if field else ""
    except (ValueError, OSError): return ""

def _base_item(category, title, message, image, duration, priority, **extra):
    return {"category": category, "title": title, "message": message, "image": image, "duration": duration, "priority": priority, **extra}

def build_display_items(config=None, device=None, category_filter=None):
    config = config or display_config(device)
    today = office_today(config)
    schedules = enabled_schedules()
    buckets = {key: [] for key in schedules if schedules[key].enabled}
    if category_filter:
        buckets = {key: items for key, items in buckets.items() if key == category_filter}

    if "birthday" in buckets:
        leap_year = today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
        policy = config.leap_day_policy if config else "feb28"
        if not leap_year and policy == "mar1" and (today.month, today.day) == (3, 1):
            birthdays = Employee.objects.filter(is_active=True).filter(Q(date_of_birth__month=3, date_of_birth__day=1) | Q(date_of_birth__month=2, date_of_birth__day=29)).order_by("name", "employee_id")
        else:
            birthdays = Employee.objects.filter(is_active=True, date_of_birth__month=today.month).order_by("name", "employee_id")
        for person in birthdays:
            matches = person.date_of_birth.day == today.day
            if person.date_of_birth.month == 2 and person.date_of_birth.day == 29 and not leap_year:
                matches = (today.month, today.day) == ((2, 28) if policy == "feb28" else (3, 1))
            if matches:
                buckets["birthday"].append(_base_item("birthday", "Happy Birthday!", config.birthday_greeting if config else "Many many happy returns of the day!", _image(person.photo), schedules["birthday"].duration, 100, name=person.name, designation=person.designation, section=person.section, person=True))

    if "anniversary" in buckets and config:
        try: milestones = {int(value.strip()) for value in config.anniversary_milestones.split(",") if value.strip()}
        except ValueError: milestones = {1, 5, 10, 15, 20, 25, 30}
        joined_filter = Q(date_of_joining__month=today.month)
        if today.year % 4 != 0 and config.leap_day_policy == "mar1" and (today.month, today.day) == (3, 1):
            joined_filter |= Q(date_of_joining__month=2, date_of_joining__day=29)
        joined_people = Employee.objects.filter(is_active=True, date_of_joining__isnull=False).filter(joined_filter).order_by("name", "employee_id")
        for person in joined_people:
            years = today.year - person.date_of_joining.year
            if years < 1 or years not in milestones: continue
            day = person.date_of_joining.day
            leap_shift = day == 29 and person.date_of_joining.month == 2 and today.year % 4 != 0 and (today.month, today.day) == ((2, 28) if config.leap_day_policy == "feb28" else (3, 1))
            if day == today.day or leap_shift:
                buckets["anniversary"].append(_base_item("anniversary", f"{years} Year{'s' if years != 1 else ''} of Service", f"Congratulations to {person.name} on this wonderful milestone!", _image(person.photo), schedules["anniversary"].duration, 90, name=person.name, designation=person.designation, section=person.section, person=True, years=years))

    now = timezone.now()
    if "recognition" in buckets:
        qs = Recognition.objects.filter(is_active=True, starts_on__lte=today, ends_on__gte=today).filter(Q(employee__isnull=True) | Q(employee__is_active=True)).select_related("employee").order_by("-priority", "starts_on", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            employee = item.employee
            buckets["recognition"].append(_base_item("recognition", item.title, item.message, _image(item.photo) or (_image(employee.photo) if employee else ""), schedules["recognition"].duration, item.priority, name=employee.name if employee else "", designation=employee.designation if employee else "", section=employee.section if employee else ""))

    if "announcement" in buckets:
        qs = Announcement.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now).order_by("-priority", "starts_at", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            buckets["announcement"].append(_base_item("announcement", item.title, item.description, _image(item.image), item.display_duration or schedules["announcement"].duration, item.priority))

    for category, model in (("safety", SafetyMessage), ("general", GeneralMessage)):
        if category not in buckets: continue
        qs = model.objects.filter(is_active=True, starts_on__lte=today, ends_on__gte=today).order_by("-priority", "starts_on", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            buckets[category].append(_base_item(category, item.title, item.message, _image(item.image), item.display_duration or schedules[category].duration, item.priority, subcategory=getattr(item, "get_category_display", lambda: "")()))

    if "fleet" in buckets:
        for locomotive in LocomotiveType.objects.filter(is_active=True).order_by("name"):
            buckets["fleet"].append(_base_item("fleet", locomotive.name, f"Present population: {locomotive.population}", _image(locomotive.photo), schedules["fleet"].duration, schedules["fleet"].priority, subcategory="Locomotive population"))

    order = sorted(buckets, key=lambda name: (-schedules[name].priority, name))
    items = []
    while any(buckets[name] for name in order):
        for name in order:
            if buckets[name]: items.append(buckets[name].pop(0))
    return items

def display_payload(config=None, device=None, category_filter=None):
    config = config or display_config(device)
    today = office_today(config)
    items = build_display_items(config, device, category_filter)
    if category_filter == "birthday" and not any(item["category"] == "birthday" for item in items):
        items = build_display_items(config, device)
    for index, item in enumerate(items):
        item["key"] = f"{item['category']}:{index}"
    date_formats = {"weekday": "%A, %d %B %Y", "short": "%d/%m/%Y", "long": "%B %d, %Y"}
    payload = {
        "items": items,
        "day": today.isoformat(),
        "date": today.strftime(date_formats.get(config.date_format, "%A, %d %B %Y") if config else "%A, %d %B %Y"),
        "office": config.office_name if config else "Your Office",
        "organization": config.organization_name if config else "Office Digital Display",
        "theme": config.theme if config else "professional",
        "transition": config.transition if config else "fade",
        "duration": config.slide_duration if config else 10,
        "refresh_interval": config.refresh_interval if config else 60,
        "logo": _image(config.logo) if config else "",
        "background": _image(config.background_image) if config else "",
        "empty_title": config.empty_title if config else "Good things happen together.",
        "empty_message": config.empty_message if config else "Wishing everyone a wonderful day.",
    }
    if not payload["items"]:
        payload["items"] = [_base_item("empty", payload["empty_title"], payload["empty_message"], "", payload["duration"], 0, key="empty:0")]
    return payload

def upcoming_anniversaries(config=None, horizon_days=31):
    config = config or DisplayConfiguration.objects.first()
    today = office_today(config)
    if not config: return []
    try: milestones = {int(value.strip()) for value in config.anniversary_milestones.split(",") if value.strip()}
    except ValueError: milestones = {1, 5, 10, 15, 20, 25, 30}
    result = []
    for person in Employee.objects.filter(is_active=True, date_of_joining__isnull=False).order_by("date_of_joining", "name"):
        joined = person.date_of_joining
        years = today.year - joined.year
        month, day = joined.month, joined.day
        if month == 2 and day == 29 and today.year % 4 != 0:
            month, day = ((2, 28) if config.leap_day_policy == "feb28" else (3, 1))
        try: occurrence = date(today.year, month, day)
        except ValueError: continue
        if occurrence < today:
            years += 1
            next_year = today.year + 1
            if month == 2 and day == 29 and next_year % 4 != 0:
                month, day = ((2, 28) if config.leap_day_policy == "feb28" else (3, 1))
            occurrence = date(next_year, month, day)
        if years in milestones and 0 <= (occurrence - today).days <= horizon_days:
            result.append({"employee": person, "years": years, "date": occurrence, "days_until": (occurrence - today).days})
    return result
