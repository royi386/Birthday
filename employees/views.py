import csv, io, os
from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import DisplayConfigurationForm, EmployeeForm
from .models import DisplayConfiguration, Employee
from signage.models import Announcement, AuditLog
from signage.services import office_today, upcoming_anniversaries

def today_local(): return office_today()
def birthdays_for(day, config=None):
    qs = Employee.objects.filter(is_active=True)
    leap = day.year % 4 == 0 and (day.year % 100 != 0 or day.year % 400 == 0)
    policy = config.leap_day_policy if config else "feb28"
    if day.month == 2 and day.day == 28 and not leap and policy == "feb28":
        return qs.filter(date_of_birth__month=2, date_of_birth__day__in=[28, 29]).order_by("name")
    if day.month == 3 and day.day == 1 and not leap and policy == "mar1":
        return qs.filter(Q(date_of_birth__month=3, date_of_birth__day=1) | Q(date_of_birth__month=2, date_of_birth__day=29)).order_by("name")
    return qs.filter(date_of_birth__month=day.month, date_of_birth__day=day.day).order_by("name")

@login_required
def dashboard(request):
    config = DisplayConfiguration.objects.first()
    today = today_local(); tomorrow = date.fromordinal(today.toordinal() + 1)
    now = timezone.now()
    announcements = Announcement.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now).count()
    stats = {"employees": Employee.objects.filter(is_active=True).count(), "today": birthdays_for(today, config).count(), "tomorrow": birthdays_for(tomorrow, config).count(), "month": Employee.objects.filter(is_active=True, date_of_birth__month=today.month).count(), "photos": Employee.objects.filter(is_active=True).exclude(photo="").count(), "anniversaries": len(upcoming_anniversaries(config)), "announcements": announcements}
    return render(request, "employees/dashboard.html", {"stats": stats, "birthdays": birthdays_for(today, config), "office_name": config.office_name if config else os.getenv("OFFICE_NAME", "Your Office")})

@login_required
@permission_required("employees.view_employee", raise_exception=True)
def employee_list(request):
    qs = Employee.objects.all(); q = request.GET.get("q", "").strip(); section = request.GET.get("section", request.GET.get("department", "")).strip()
    if q: qs = qs.filter(Q(name__icontains=q) | Q(employee_id__icontains=q))
    if section: qs = qs.filter(section__iexact=section)
    sections = Employee.objects.exclude(section="").values_list("section", flat=True).distinct().order_by("section")
    return render(request, "employees/list.html", {"page": Paginator(qs, 25).get_page(request.GET.get("page")), "q": q, "section": section, "sections": sections})

@login_required
def employee_edit(request, pk=None):
    required_perm = "employees.change_employee" if pk else "employees.add_employee"
    if not request.user.has_perm(required_perm): raise PermissionDenied
    employee = get_object_or_404(Employee, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, request.FILES or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        saved = form.save(); AuditLog.objects.create(actor=request.user, action="update" if employee else "create", target=str(saved), summary=f"Employee {'updated' if employee else 'created'}: {saved.name} ({saved.employee_id})"); messages.success(request, "Employee saved."); return redirect("employee_list")
    return render(request, "employees/form.html", {"form": form, "employee": employee})

@login_required
@permission_required("employees.change_employee", raise_exception=True)
@require_POST
def employee_deactivate(request, pk):
    employee = get_object_or_404(Employee, pk=pk); employee.is_active = False; employee.save(update_fields=["is_active", "updated_at"])
    AuditLog.objects.create(actor=request.user, action="deactivate", target=str(employee), summary=f"Employee deactivated: {employee.name} ({employee.employee_id})")
    messages.success(request, f"{employee.name} was deactivated."); return redirect("employee_list")

@login_required
@permission_required("employees.add_employee", raise_exception=True)
def employee_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8"); response["Content-Disposition"] = 'attachment; filename="employee-import-template.csv"'
    writer = csv.writer(response); writer.writerow(["employee_id", "name", "designation", "section", "date_of_birth", "date_of_joining", "is_active"]); writer.writerow(["E001", "Asha Kumar", "Analyst", "Traction", "1990-05-14", "2020-02-01", "true"]); return response

@login_required
@permission_required("employees.add_employee", raise_exception=True)
def employee_template_xlsx(request):
    from io import BytesIO
    from openpyxl import Workbook
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Employees"
    sheet.append(["employee_id", "name", "designation", "section", "date_of_birth", "date_of_joining", "is_active"])
    sheet.append(["E001", "Asha Kumar", "Analyst", "Traction", "1990-05-14", "2020-02-01", "true"])
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = max(16, min(32, max(len(str(cell.value or "")) for cell in column) + 2))
    file_data = BytesIO(); workbook.save(file_data)
    response = HttpResponse(file_data.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="employee-import-template.xlsx"'
    return response

def parse_date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if not value: return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try: return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError: pass
    return None

def parse_import_file(upload):
    raw = upload.read()
    if len(raw) > 5 * 1024 * 1024: raise ValueError("File must be under 5 MB.")
    if upload.name.lower().endswith(".csv"): rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    elif upload.name.lower().endswith(".xlsx"):
        from openpyxl import load_workbook
        values = list(load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active.values)
        if not values: return []
        headers = [str(v or "").strip().lower() for v in values[0]]; rows = [dict(zip(headers, row)) for row in values[1:] if any(v is not None for v in row)]
    else: raise ValueError("Choose a .csv or .xlsx file.")
    return [{str(k).strip().lower(): v for k, v in row.items() if k} for row in rows]

def import_preview(rows):
    seen, valid, errors = set(), [], []
    for i, source in enumerate(rows, start=2):
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in source.items()}; err = []
        for key in ("employee_id", "name", "date_of_birth"):
            if not row.get(key): err.append(f"Missing {key}")
        empid = str(row.get("employee_id", ""))
        if empid in seen and empid: err.append("Duplicate ID in file")
        if empid: seen.add(empid)
        dob = parse_date(row.get("date_of_birth")); joining = parse_date(row.get("date_of_joining")) if row.get("date_of_joining") else None
        if row.get("date_of_birth") and not dob: err.append("Invalid date_of_birth (use YYYY-MM-DD)")
        if row.get("date_of_joining") and not joining: err.append("Invalid date_of_joining (use YYYY-MM-DD)")
        if dob and dob > today_local(): err.append("date_of_birth cannot be in the future")
        if joining and joining > today_local(): err.append("date_of_joining cannot be in the future")
        exists = Employee.objects.filter(employee_id=empid).exists() if empid else False
        if err: errors.append({"line": i, "employee_id": empid, "errors": err})
        else: valid.append({"employee_id": empid, "name": str(row["name"]), "designation": str(row.get("designation") or ""), "section": str(row.get("section") or row.get("department") or ""), "date_of_birth": dob.isoformat(), "date_of_joining": joining.isoformat() if joining else "", "is_active": str(row.get("is_active", "true")).lower() not in ("false", "0", "no", "inactive"), "exists": exists})
    return valid, errors

@login_required
@permission_required("employees.add_employee", raise_exception=True)
def employee_import(request):
    if request.method == "POST":
        try: valid, errors = import_preview(parse_import_file(request.FILES["file"]))
        except Exception as exc:
            messages.error(request, f"Could not read import: {exc}"); return redirect("employee_import")
        request.session["employee_import_rows"], request.session["employee_import_errors"] = valid, errors
        return render(request, "employees/import_preview.html", {"rows": valid, "errors": errors})
    return render(request, "employees/import.html")

@login_required
@permission_required("employees.add_employee", raise_exception=True)
@require_POST
def employee_import_confirm(request):
    if request.POST.get("update_existing") == "yes" and not request.user.has_perm("employees.change_employee"):
        raise PermissionDenied
    rows = request.session.pop("employee_import_rows", []); errors = request.session.pop("employee_import_errors", [])
    if not rows: messages.error(request, "No valid rows were ready to import."); return redirect("employee_import")
    count = 0
    for row in rows:
        if row["exists"] and request.POST.get("update_existing") != "yes": continue
        Employee.objects.update_or_create(employee_id=row["employee_id"], defaults={"name": row["name"], "designation": row["designation"], "section": row["section"], "date_of_birth": row["date_of_birth"], "date_of_joining": row["date_of_joining"] or None, "is_active": row["is_active"]}); count += 1
    if count: AuditLog.objects.create(actor=request.user, action="import", target="Employee import", summary=f"Imported or updated {count} employee records.")
    if errors:
        response = HttpResponse(content_type="text/csv; charset=utf-8"); response["Content-Disposition"] = 'attachment; filename="employee-import-errors.csv"'; writer = csv.writer(response); writer.writerow(["line", "employee_id", "errors"])
        for error in errors: writer.writerow([error["line"], error["employee_id"], "; ".join(error["errors"])])
        return response
    messages.success(request, f"Imported or updated {count} employee records."); return redirect("employee_list")

@login_required
@permission_required("employees.add_employee", raise_exception=True)
def employee_import_errors(request):
    errors = request.session.get("employee_import_errors", [])
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="employee-import-errors.csv"'
    writer = csv.writer(response); writer.writerow(["line", "employee_id", "errors"])
    for error in errors: writer.writerow([error["line"], error["employee_id"], "; ".join(error["errors"])])
    return response

@login_required
@permission_required("employees.manage_displayconfiguration", raise_exception=True)
def display_settings(request):
    config = DisplayConfiguration.objects.first() or DisplayConfiguration()
    form = DisplayConfigurationForm(request.POST or None, request.FILES or None, instance=config)
    if request.method == "POST" and form.is_valid():
        saved = form.save(); AuditLog.objects.create(actor=request.user, action="configuration", target=saved.office_name, summary="Updated display configuration."); messages.success(request, "Display settings saved."); return redirect("display_settings")
    return render(request, "employees/display_settings.html", {"form": form})

def display_context():
    today = today_local(); items = [{"name": e.name, "designation": e.designation, "section": e.section, "photo": e.photo.url if e.photo else "", "greeting": "HAPPY BIRTHDAY!"} for e in birthdays_for(today)]
    config = DisplayConfiguration.objects.first()
    try: duration = config.slide_duration if config else max(5, min(30, int(os.getenv("BIRTHDAY_SLIDE_SECONDS", "10"))))
    except ValueError: duration = 10
    return {"items": items, "day": today.isoformat(), "date": today.strftime("%A, %d %B %Y"), "office": config.office_name if config else os.getenv("OFFICE_NAME", "Your Office"), "greeting": config.birthday_greeting if config else os.getenv("BIRTHDAY_GREETING", "Many many happy returns of the day!"), "duration": duration, "theme": config.theme if config else "professional"}
def display_home(request): return redirect("display_birthdays")
def display_birthdays(request): return render(request, "display/birthdays.html", display_context())
def birthday_feed(request):
    response = JsonResponse(display_context()); response["Cache-Control"] = "no-store"; return response
def service_worker(request):
    js = "const CACHE='odds-v1';self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/display/birthdays/']))));self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{if(r.ok&&(e.request.url.includes('/media/')||e.request.url.includes('/display/birthdays/'))){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));}return r;}).catch(()=>caches.match(e.request)));});"
    return HttpResponse(js, content_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})
def health(request): return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})
