import shutil
import tempfile
import calendar
import logging
from pathlib import Path
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.db import transaction
from django.db import connection
from django.forms import modelformset_factory
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from employees.forms import DisplayConfigurationForm
from employees.models import DisplayConfiguration, Employee
from .forms import AnnouncementForm, ContentScheduleForm, DisplayDeviceForm, GeneralMessageForm, LocomotiveTypeForm, RecognitionForm, SafetyMessageForm
from .models import Announcement, AuditLog, ContentSchedule, DisplayDevice, GeneralMessage, LocomotiveType, Recognition, SafetyMessage
from .services import display_config, display_payload, office_today, upcoming_anniversaries
from .backup import create_backup

CONTENT_SECTIONS = {
    "recognition": {"title": "Employee recognition", "model": Recognition, "form": RecognitionForm, "perm": "recognition"},
    "announcements": {"title": "Office announcements", "model": Announcement, "form": AnnouncementForm, "perm": "announcement"},
    "safety": {"title": "Safety messages", "model": SafetyMessage, "form": SafetyMessageForm, "perm": "safetymessage"},
    "general": {"title": "General information", "model": GeneralMessage, "form": GeneralMessageForm, "perm": "generalmessage"},
}
logger = logging.getLogger(__name__)


def audit(actor, action, target, summary):
    AuditLog.objects.create(actor=actor if getattr(actor, "is_authenticated", False) else None, action=action, target=str(target)[:180], summary=str(summary)[:500])

def _section(section):
    try: return CONTENT_SECTIONS[section]
    except KeyError: raise Http404

@login_required
def anniversaries(request):
    if not request.user.has_perm("employees.view_employee"): raise PermissionDenied
    config = DisplayConfiguration.objects.first()
    today = office_today(config)
    upcoming = upcoming_anniversaries(config)
    due_today = [item for item in upcoming if item["days_until"] == 0]
    return render(request, "signage/anniversaries.html", {"today": today, "due_today": due_today, "upcoming": [item for item in upcoming if item["days_until"] > 0], "milestones": config.anniversary_milestones if config else "1,5,10,15,20,25,30"})

@login_required
def birthday_management(request):
    if not request.user.has_perm("employees.view_employee"): raise PermissionDenied
    config = DisplayConfiguration.objects.first()
    today = office_today(config)
    month = int(request.GET.get("month", today.month))
    if month < 1 or month > 12: month = today.month
    employees = Employee.objects.filter(is_active=True, date_of_birth__month=month).order_by("date_of_birth__day", "name")
    return render(request, "signage/birthdays.html", {"employees": employees, "month": month, "today": today, "months": [(n, calendar.month_name[n]) for n in range(1, 13)]})

@login_required
def content_list(request, section):
    definition = _section(section)
    if not request.user.has_perm(f"signage.view_{definition['perm']}"): raise PermissionDenied
    qs = definition["model"].objects.all().order_by("-is_active", "-priority", "pk")
    if section == "recognition": qs = qs.select_related("employee").prefetch_related("configurations")
    q = request.GET.get("q", "").strip()
    if q: qs = qs.filter(title__icontains=q)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    if section == "recognition":
        for item in page:
            item.employee_photo = item.employee.photo if item.employee_id and item.employee.photo else None
            item.work_photo = item.photo if item.photo else None
            item.display_targets = list(item.configurations.all())
    return render(request, "signage/content_list.html", {"section": section, "definition": definition, "page": page, "q": q, "add_url": reverse("content_add", kwargs={"section": section})})

@login_required
def content_edit(request, section, pk=None):
    definition = _section(section)
    required = f"signage.change_{definition['perm']}" if pk else f"signage.add_{definition['perm']}"
    if not request.user.has_perm(required): raise PermissionDenied
    obj = definition["model"].objects.filter(pk=pk).first() if pk else None
    if pk and obj is None: raise Http404
    form = definition["form"](request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic(): saved = form.save()
        try:
            audit(request.user, "update" if obj else "create", saved, f"{definition['title']}: {saved}")
        except Exception:
            logger.exception("Could not write audit entry for %s", definition["title"])
            messages.warning(request, f"{definition['title']} was saved, but its audit entry could not be recorded.")
        else:
            messages.success(request, f"{definition['title']} saved.")
        return redirect("content_list", section=section)
    return render(request, "signage/content_form.html", {"section": section, "definition": definition, "form": form, "obj": obj})

@login_required
@require_POST
def content_toggle(request, section, pk):
    definition = _section(section)
    if not request.user.has_perm(f"signage.change_{definition['perm']}"): raise PermissionDenied
    obj = get_object_or_404(definition["model"], pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    audit(request.user, "activate" if obj.is_active else "deactivate", obj, f"{definition['title']}: {obj}")
    messages.success(request, f"{obj} was {'activated' if obj.is_active else 'deactivated'}.")
    return redirect("content_list", section=section)

@login_required
def display_configurations(request):
    if not request.user.has_perm("employees.manage_displayconfiguration"): raise PermissionDenied
    return render(request, "signage/configurations.html", {"configurations": DisplayConfiguration.objects.all().order_by("office_name", "pk")})

@login_required
def display_configuration_edit(request, pk=None):
    required = "employees.change_displayconfiguration" if pk else "employees.add_displayconfiguration"
    if not request.user.has_perm("employees.manage_displayconfiguration") and not request.user.has_perm(required): raise PermissionDenied
    obj = get_object_or_404(DisplayConfiguration, pk=pk) if pk else None
    form = DisplayConfigurationForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        audit(request.user, "update" if obj else "create", saved, f"Display configuration: {saved.office_name}")
        messages.success(request, "Display configuration saved.")
        return redirect("display_configurations")
    return render(request, "employees/display_settings.html", {"form": form, "configuration": obj})

@login_required
def system_settings(request):
    if not (request.user.is_superuser or request.user.has_perm("signage.change_contentschedule")): raise PermissionDenied
    ScheduleSet = modelformset_factory(ContentSchedule, form=ContentScheduleForm, extra=0)
    formset = ScheduleSet(request.POST or None, queryset=ContentSchedule.objects.all().order_by("-priority", "category"))
    if request.method == "POST" and formset.is_valid():
        formset.save()
        audit(request.user, "schedule", "Content schedule", "Updated category enablement, priority and duration settings.")
        messages.success(request, "Content schedule saved.")
        return redirect("system_settings")
    return render(request, "signage/system_settings.html", {"formset": formset, "audit_entries": AuditLog.objects.select_related("actor")[:40], "categories": ContentSchedule.CATEGORY_CHOICES})

@login_required
def display_devices(request):
    if not request.user.has_perm("signage.view_displaydevice"): raise PermissionDenied
    devices = DisplayDevice.objects.select_related("configuration").all().order_by("name")
    return render(request, "signage/devices.html", {"devices": devices})

@login_required
def display_device_edit(request, pk=None):
    required = "signage.change_displaydevice" if pk else "signage.add_displaydevice"
    if not request.user.has_perm(required): raise PermissionDenied
    obj = get_object_or_404(DisplayDevice, pk=pk) if pk else None
    form = DisplayDeviceForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        device = form.save()
        audit(request.user, "update" if obj else "create", device, f"Display device: {device.name}")
        messages.success(request, "Display device saved.")
        return redirect("display_devices")
    return render(request, "signage/device_form.html", {"form": form, "device": obj})

@login_required
def display_device_toggle(request, pk):
    if not request.user.has_perm("signage.change_displaydevice"): raise PermissionDenied
    if request.method != "POST": raise Http404
    device = get_object_or_404(DisplayDevice, pk=pk)
    device.is_enabled = not device.is_enabled
    device.save(update_fields=["is_enabled"])
    audit(request.user, "enable" if device.is_enabled else "disable", device, f"Display device {device.display_id}")
    return redirect("display_devices")

@login_required
def locomotive_types(request):
    if not request.user.has_perm("signage.view_locomotivetype"): raise PermissionDenied
    return render(request, "signage/locomotive_types.html", {"locomotives": LocomotiveType.objects.all()})

@login_required
def locomotive_type_edit(request, pk=None):
    required = "signage.change_locomotivetype" if pk else "signage.add_locomotivetype"
    if not request.user.has_perm(required): raise PermissionDenied
    obj = get_object_or_404(LocomotiveType, pk=pk) if pk else None
    form = LocomotiveTypeForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        locomotive = form.save()
        audit(request.user, "update" if obj else "create", locomotive, f"Locomotive population: {locomotive.name} = {locomotive.population}")
        messages.success(request, "Locomotive type saved.")
        return redirect("locomotive_types")
    return render(request, "signage/locomotive_form.html", {"form": form, "locomotive": obj})

@login_required
@require_POST
def locomotive_type_toggle(request, pk):
    if not request.user.has_perm("signage.change_locomotivetype"): raise PermissionDenied
    locomotive = get_object_or_404(LocomotiveType, pk=pk)
    locomotive.is_active = not locomotive.is_active
    locomotive.save(update_fields=["is_active", "updated_at"])
    audit(request.user, "activate" if locomotive.is_active else "deactivate", locomotive, f"Locomotive type {locomotive.name}")
    messages.success(request, f"{locomotive.name} was {'activated' if locomotive.is_active else 'deactivated'}.")
    return redirect("locomotive_types")

@login_required
def backup_download(request):
    if not request.user.is_staff: raise PermissionDenied
    temp_dir = Path(tempfile.mkdtemp(prefix="odds-backup-"))
    archive = temp_dir / "odds-backup.zip"
    create_backup(archive)
    audit(request.user, "backup", archive.name, "Created a database and media backup archive.")
    response = FileResponse(archive.open("rb"), as_attachment=True, filename=f"odds-backup-{timezone.now():%Y%m%d-%H%M%S}.zip", content_type="application/zip")
    response._resource_closers.append(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
    return response

def public_display(request, device_id=None, category_filter=None):
    device = None
    if device_id:
        device = get_object_or_404(DisplayDevice, display_id=device_id, is_enabled=True)
        device.mark_seen()
    config = display_config(device)
    payload = display_payload(config, device, category_filter)
    return render(request, "display/birthdays.html", payload)

def display_feed(request, device_id=None, category_filter=None):
    device = None
    if device_id:
        device = get_object_or_404(DisplayDevice, display_id=device_id, is_enabled=True)
        device.mark_seen()
    response = JsonResponse(display_payload(display_config(device), device, category_filter), encoder=DjangoJSONEncoder)
    response["Cache-Control"] = "no-store"
    return response

def service_worker(request):
    js = """const CACHE='odds-display-v7';self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/display/']))));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('odds-display-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener('message',e=>{if(e.data?.type==='CACHE_URL'&&e.data.url)e.waitUntil(caches.open(CACHE).then(c=>c.add(e.data.url).catch(()=>{})))});self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin)return;e.respondWith(fetch(e.request).then(r=>{if(r.ok&&(u.pathname.startsWith('/display/')||u.pathname.startsWith('/media/')||u.pathname.startsWith('/static/'))&&!u.pathname.endsWith('.json')){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));}return r;}).catch(()=>caches.match(e.request)));});"""
    return HttpResponse(js, content_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

def health(request):
    try:
        with connection.cursor() as cursor: cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})
