from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Q
from django.utils import timezone
from employees.models import DisplayConfiguration, Employee
from .models import Announcement, ContentSchedule, DisplayHoliday, DisplayOffSchedule, FullScreenPhoto, GeneralMessage, LocomotiveType, Recognition, SafetyMessage

DEFAULT_SCHEDULE = {
    "birthday": (True, 100, 10), "anniversary": (True, 90, 10),
    "safety": (True, 85, 15), "recognition": (True, 70, 15),
    "announcement": (True, 60, 15), "photos": (True, 50, 10),
    "general": (True, 40, 15), "fleet": (True, 1, 10),
}

def office_today(config=None):
    config = config or DisplayConfiguration.objects.first()
    zone = ZoneInfo(config.timezone_name) if config else ZoneInfo("Asia/Kolkata")
    return timezone.localdate(timezone.now(), zone)

def display_on_active(config=None, now=None):
    schedule = DisplayOffSchedule.objects.first()
    if not schedule or not schedule.schedule_enabled:
        return True
    config = config or DisplayConfiguration.objects.first()
    zone = ZoneInfo(config.timezone_name) if config else ZoneInfo("Asia/Kolkata")
    local_now = timezone.localtime(now or timezone.now(), zone)
    rules = schedule.weekday_rules or {}
    for offset in (-1, 0):
        start_day = local_now.date() + timedelta(days=offset)
        rule = rules.get(str(start_day.weekday()), {})
        if not rule.get("enabled"):
            continue
        try:
            start_time = time.fromisoformat(rule["start"])
            end_time = time.fromisoformat(rule["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time == end_time:
            continue
        end_day = start_day if start_time < end_time else start_day + timedelta(days=1)
        start = datetime.combine(start_day, start_time, tzinfo=zone)
        end = datetime.combine(end_day, end_time, tzinfo=zone)
        if start <= local_now < end:
            return True
    return False

def display_off_active(config=None, now=None):
    return not display_on_active(config, now)

def next_display_off_change(config=None, now=None):
    schedule = DisplayOffSchedule.objects.first()
    if not schedule or not schedule.schedule_enabled:
        return ""
    config = config or DisplayConfiguration.objects.first()
    zone = ZoneInfo(config.timezone_name) if config else ZoneInfo("Asia/Kolkata")
    local_now = timezone.localtime(now or timezone.now(), zone)
    boundaries = []
    for offset in range(-1, 8):
        start_day = local_now.date() + timedelta(days=offset)
        rule = (schedule.weekday_rules or {}).get(str(start_day.weekday()), {})
        if not rule.get("enabled"):
            continue
        try:
            start_time = time.fromisoformat(rule["start"])
            end_time = time.fromisoformat(rule["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time == end_time:
            continue
        start = datetime.combine(start_day, start_time, tzinfo=zone)
        end_day = start_day if start_time < end_time else start_day + timedelta(days=1)
        end = datetime.combine(end_day, end_time, tzinfo=zone)
        if start > local_now:
            boundaries.append(start)
        if end > local_now:
            boundaries.append(end)
    return min(boundaries).isoformat() if boundaries else ""

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

def _employee_images(employee):
    return [record["image"] for record in _employee_photo_records(employee)]

def _employee_profile_photo_record(employee):
    if employee is None:
        return {"image": "", "photo_kind": "", "photo_id": "", "photo_position_x": 50, "photo_position_y": 50, "photo_zoom": 160}
    return {"image": _image(employee.photo), "photo_kind": "employee", "photo_id": employee.pk, "photo_position_x": employee.photo_position_x, "photo_position_y": employee.photo_position_y, "photo_zoom": employee.photo_zoom}

def _employee_photo_records(employee):
    if employee is None: return [_employee_profile_photo_record(None)]
    photos = [(employee.photo, "employee", employee.pk, employee.photo_position_x, employee.photo_position_y, employee.photo_zoom)]
    photos.extend((photo.photo, "gallery", photo.pk, photo.photo_position_x, photo.photo_position_y, photo.photo_zoom) for photo in employee.gallery_photos.all())
    records, seen = [], set()
    for field, kind, photo_id, x, y, zoom in photos:
        image = _image(field)
        if image and image not in seen:
            records.append({"image": image, "photo_kind": kind, "photo_id": photo_id, "photo_position_x": x, "photo_position_y": y, "photo_zoom": zoom})
            seen.add(image)
    return records or [_employee_profile_photo_record(employee)]

def _base_item(category, title, message, image, duration, priority, **extra):
    return {"category": category, "title": title, "message": message, "image": image, "duration": duration, "priority": priority, **extra}

def birthday_observances(on_date, config=None):
    tomorrow = on_date + timedelta(days=1)
    target_days = {on_date, tomorrow}
    policy = config.leap_day_policy if config else "feb28"
    target_months = {on_date.month, tomorrow.month}
    if policy == "mar1" and any((day.month, day.day) == (3, 1) for day in target_days):
        target_months.add(2)
    holidays = set(DisplayHoliday.objects.filter(is_active=True, date__in=target_days).values_list("date", flat=True))
    birthdays = Employee.objects.filter(
        is_active=True, date_of_birth__month__in=target_months,
    ).prefetch_related("gallery_photos").order_by("name", "employee_id")
    result = []
    for person in birthdays:
        is_advance = False
        for year in {on_date.year, tomorrow.year}:
            leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
            month, day = person.date_of_birth.month, person.date_of_birth.day
            if month == 2 and day == 29 and not leap_year:
                month, day = (2, 28) if policy == "feb28" else (3, 1)
            event_day = date(year, month, day)
            if event_day in target_days:
                advance = event_day.weekday() == 6 or event_day in holidays
                if event_day - timedelta(days=1 if advance else 0) == on_date:
                    is_advance = advance
                    result.append((person, is_advance))
                    break
    return result

def build_display_items(config=None, device=None, category_filter=None):
    config = config or display_config(device)
    today = office_today(config)
    schedules = enabled_schedules()
    buckets = {key: [] for key in schedules if schedules[key].enabled}
    if category_filter:
        buckets = {key: items for key, items in buckets.items() if key == category_filter}

    if "birthday" in buckets:
        for person, advance in birthday_observances(today, config):
            for photo in _employee_photo_records(person):
                slide = _base_item(
                    "birthday", "Advance Happy Birthday!" if advance else "Happy Birthday!",
                    config.birthday_greeting if config else "Many many happy returns of the day!",
                    photo["image"], schedules["birthday"].duration, 100,
                    name=person.name, designation=person.designation, section=person.section,
                    person=True, celebration_variant=((person.pk - 1) % 4) + 1,
                    photo_kind=photo["photo_kind"], photo_id=photo["photo_id"], photo_position_x=photo["photo_position_x"], photo_position_y=photo["photo_position_y"], photo_zoom=photo["photo_zoom"],
                )
                if advance:
                    slide.update({"is_advance": True, "subcategory": "Advance wishes"})
                buckets["birthday"].append(slide)

    if "anniversary" in buckets and config:
        try: milestones = {int(value.strip()) for value in config.anniversary_milestones.split(",") if value.strip()}
        except ValueError: milestones = {1, 5, 10, 15, 20, 25, 30}
        joined_filter = Q(date_of_joining__month=today.month)
        if today.year % 4 != 0 and config.leap_day_policy == "mar1" and (today.month, today.day) == (3, 1):
            joined_filter |= Q(date_of_joining__month=2, date_of_joining__day=29)
        joined_people = Employee.objects.filter(is_active=True, date_of_joining__isnull=False).filter(joined_filter).prefetch_related("gallery_photos").order_by("name", "employee_id")
        for person in joined_people:
            years = today.year - person.date_of_joining.year
            if years < 1 or years not in milestones: continue
            day = person.date_of_joining.day
            leap_shift = day == 29 and person.date_of_joining.month == 2 and today.year % 4 != 0 and (today.month, today.day) == ((2, 28) if config.leap_day_policy == "feb28" else (3, 1))
            if day == today.day or leap_shift:
                photo = _employee_profile_photo_record(person)
                buckets["anniversary"].append(_base_item("anniversary", f"{years} Year{'s' if years != 1 else ''} of Service", f"Congratulations to {person.name} on this wonderful milestone!", photo["image"], schedules["anniversary"].duration, 90, name=person.name, designation=person.designation, section=person.section, person=True, years=years, celebration_variant=((person.pk - 1) % 4) + 1, photo_kind=photo["photo_kind"], photo_id=photo["photo_id"], photo_position_x=photo["photo_position_x"], photo_position_y=photo["photo_position_y"], photo_zoom=photo["photo_zoom"]))

    now = timezone.now()
    if "recognition" in buckets:
        qs = Recognition.objects.filter(is_active=True, starts_on__lte=today, ends_on__gte=today).filter(Q(employee__isnull=True) | Q(employee__is_active=True)).select_related("employee").prefetch_related("employee__gallery_photos").order_by("-priority", "starts_on", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            employee = item.employee
            work_image = _image(item.photo)
            photo = _employee_profile_photo_record(employee)
            buckets["recognition"].append(_base_item("recognition", item.title, item.message, photo["image"] or work_image, schedules["recognition"].duration, item.priority, name=employee.name if employee else "", designation=employee.designation if employee else "", section=employee.section if employee else "", person=employee is not None, employee_image=photo["image"], work_image=work_image, photo_kind=photo["photo_kind"], photo_id=photo["photo_id"], photo_position_x=photo["photo_position_x"], photo_position_y=photo["photo_position_y"], photo_zoom=photo["photo_zoom"], recognition_id=item.pk, work_photo_position_x=item.photo_position_x, work_photo_position_y=item.photo_position_y, work_photo_zoom=item.photo_zoom))

    if "announcement" in buckets:
        qs = Announcement.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now).order_by("-priority", "starts_at", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            buckets["announcement"].append(_base_item("announcement", item.title, item.description, _image(item.image), item.display_duration or schedules["announcement"].duration, item.priority))

    for category, model in (("safety", SafetyMessage), ("general", GeneralMessage)):
        if category not in buckets: continue
        qs = model.objects.filter(is_active=True, starts_on__lte=today, ends_on__gte=today).order_by("-priority", "starts_on", "pk")
        for item in _is_configured_for(qs, "configurations", config):
            buckets[category].append(_base_item(category, item.title, item.message, _image(item.image), item.display_duration or schedules[category].duration, item.priority, subcategory=getattr(item, "get_category_display", lambda: "")()))

    if "photos" in buckets:
        for photo in FullScreenPhoto.objects.all():
            buckets["photos"].append(_base_item(
                "photos", "Full screen photo", "", _image(photo.photo),
                schedules["photos"].duration, schedules["photos"].priority,
            ))

    if "fleet" in buckets:
        locomotives = list(LocomotiveType.objects.filter(is_active=True).order_by("name"))
        if locomotives:
            buckets["fleet"].append(_base_item(
                "fleet", "Locomotive population",
                "", "", schedules["fleet"].duration,
                schedules["fleet"].priority,
                subcategory="Fleet information",
                locomotives=[{"name": loco.name, "population": loco.population, "image": _image(loco.photo)} for loco in locomotives],
            ))

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
        "timezone_name": config.timezone_name if config else "Asia/Kolkata",
        "display_off": display_off_active(config),
        "next_display_off_change": next_display_off_change(config),
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
