# Office Digital Display System (ODDS)

ODDS is a Django-based employee portal and digital-signage scheduler. It manages birthdays, work anniversaries, employee recognition, office announcements, safety messages and general information, and locomotive population, then rotates eligible slides on public TV routes. Admin routes require authentication and model permissions; display routes are read-only.

## Architecture

- **`employees` app:** employee directory, photos, birthdays, display profiles and XLSX/CSV import.
- **`signage` app:** recognition, announcements, safety/general content, schedule categories, display devices, audit log and backup tooling.
- **`signage.services`:** office-timezone date calculation, anniversary milestones, publication-window filtering and fair category rotation. Items within a category use their priority; enabled categories rotate in priority order so a birthday queue cannot permanently starve safety content.
- **Database:** SQLite by default. The models and settings also support PostgreSQL through `DATABASE_ENGINE` and `POSTGRES_*` environment variables.
- **Uploads/static assets:** employee and content images live in `MEDIA_ROOT`; WhiteNoise serves collected static assets. Docker uses named persistent volumes.

## Run locally

Requires Python 3.12 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_DEBUG = "True"
python manage.py migrate
python manage.py ensure_default_admin
python manage.py runserver 127.0.0.1:5175
```

Open `http://127.0.0.1:5175/`. The shared TV route is `http://127.0.0.1:5175/display/`; `/display/birthdays/` is a compatibility route to the same scheduled rotation.

## Docker deployment

The GitHub Actions workflow publishes `ghcr.io/royi386/birthday:latest` after each push to `master`. The server needs only `docker-compose.yml` and Docker Compose; it does not need the application source tree or an `.env` file. Deploy the newest image with:

```sh
docker compose pull
docker compose up -d
```

The app listens on port **5175** on all host interfaces. Open `http://SERVER:5175/` from another PC on the same LAN. Startup applies migrations and collects static files. The service restarts unless stopped, and `/health/` is the Compose health check. Database and media use persistent named volumes. Django generates its secret key on first startup and stores it in the data volume. Keep this deployment on the trusted office LAN; do not expose port 5175 to the public internet. If the GHCR package is private, authenticate once on the server with `docker login ghcr.io` before pulling.

### PostgreSQL option

Use an external PostgreSQL server or add one to your deployment. Set:

```env
DATABASE_ENGINE=django.db.backends.postgresql
POSTGRES_DB=odds
POSTGRES_USER=odds
POSTGRES_PASSWORD=your-database-password
POSTGRES_HOST=database-host
POSTGRES_PORT=5432
```

The bundled Compose file starts only the web app; configure PostgreSQL service networking, health dependencies and backups for your environment before switching a live installation.

## Demo records

For a safe functional preview, create three clearly labeled fictitious employees (birthday today, birthday tomorrow and leap-day birthday) with `python manage.py load_demo_data`. The command is idempotent for `DEMO-*` IDs; delete those sample rows before importing real employee data. It does not create demo records automatically.

## Accounts and permissions

On the first startup, the app creates the initial superuser `admin` with password `admin` if no `admin` account exists. Change this password after the first login. Existing accounts and passwords are never reset on later startups. Add operational users in `/admin/` under **Users and permissions**. Grant only the permissions needed for each role:

- Employee directory: `view_employee`, `add_employee`, `change_employee` (and `delete_employee` only if hard deletion is required).
- Display profile management: `manage_displayconfiguration`.
- Each content type: its `view_*`, `add_*` and `change_*` permissions.
- Schedule/audit: `change_contentschedule` and `view_auditlog`.
- Display devices: `view_displaydevice`, `add_displaydevice`, `change_displaydevice`.
- Backup download: Django staff status.

All write routes check permissions. Public display and JSON feed endpoints expose only slide text, employee name/role/section and necessary images; they never return date of birth, employee number or age.

## Employees and spreadsheet import

The employee directory supports add/edit/deactivate, name/ID search, section filtering, pagination, photo replacement and unique employee IDs. Dates of birth and joining dates cannot be in the future. Images are checked by content as valid JPEG/PNG/WebP files and limited to 10 MB; MPO photos are accepted as JPEG-compatible files. Multipart requests allow extra space for form data.

In **Import employees**, download the CSV or Excel template, upload `.csv` or `.xlsx`, review row validation, then confirm. Required columns are `employee_id`, `name`, `date_of_birth`; optional columns are `designation`, `section`, `date_of_joining`, `is_active`. ISO dates (`YYYY-MM-DD`) are recommended. The preview reports missing fields, duplicate IDs, invalid/future dates and existing records. Existing IDs are skipped by default; overwriting them requires selecting the update option and the user's `change_employee` permission. Invalid rows can be downloaded as a CSV error report. Photos are added on employee profiles rather than in the spreadsheet.

## Signage content and scheduler

Administrators can manage:

- **Birthdays:** automatic month/day matching for active employees; configurable February 29 policy (February 28 or March 1); one slide per person; initials fallback when a photo is missing.
- **Work anniversaries:** calculated from a valid date of joining, using configurable service milestones. The anniversary page shows today's and next 31 days' milestones.
- **Employee recognition:** employee link, achievement, message, optional photo override, publication dates, priority and active state.
- **Announcements:** title, description/image, start/end date-time, duration, priority and active state.
- **Safety messages:** text/poster, category, start/end dates, duration, priority and active state.
- **General information:** scheduled text/image slides for other office content.

Active locomotive types display their current population every day as the lowest-priority category. Manage them under **Locomotive population**; each type supports a photo, present count and active status.

Each content item can be global or assigned to selected display profiles. Expired and inactive entries are excluded automatically. **System settings** controls category enablement, relative priority and slide durations. Categories rotate fairly; birthdays appear early in each pass while safety messages still get rotation time. Defaults are 10 seconds for birthdays/anniversaries and 15 seconds for other content.

## Display configuration and kiosk

Create one or more display profiles with organization/office names, logo/background, theme, birthday greeting, transition, date format, timezone, refresh interval, empty-day text, leap-day policy and anniversary milestones. Three themes are included: Professional Blue & Gold, Elegant Celebration and Minimal Corporate.

- Shared office TV: `/display/`
- Compatibility birthday URL: `/display/birthdays/` (also rotates scheduled office content)
- Device-specific URL: `/display/device/<display-id>/`
- Read-only JSON feed: `/display/feed.json` or `/display/device/<display-id>/feed.json`
- Admin preview: `/display-preview/`

Register devices under **Display devices**, assign a profile, and use the generated URL on each kiosk. Device status is based on its last feed request (online threshold: three minutes). Disabled devices return 404.

The public display is full-screen responsive and needs no interaction. Slides loop using their configured durations. It polls for changes and applies new content at a slide boundary to avoid interrupting a slide. A root-scoped service worker caches the active display page and media after first online use, serves that cached page during network loss, shows an unobtrusive offline badge, and retries automatically. Service workers require HTTPS except on localhost. Launch the TV browser in kiosk mode, for example:

```sh
chromium --kiosk http://SERVER:5175/display/
```

Configure OS auto-login, startup launch, sleep/screen-saver settings and BIOS AC restoration separately on the mini PC; those host settings cannot be changed by the web application.

## Backups and restore

Staff can download a database-fixture plus media ZIP from **System settings**. It is ZIP-integrity checked before delivery. Automated daily backups are available through the Compose `backup` profile; set `BACKUP_INTERVAL_SECONDS` to change the default 86400-second interval:

```sh
docker compose --profile backup pull
docker compose --profile backup up -d
docker compose logs -f backup
```

The backup service writes verified archives to the persistent `odds-backups` volume. To list them, copy the volume contents to a host folder with a temporary Alpine container. For a fixture restore, stop the app, extract a chosen archive, then restore into a fresh/empty application database and media volume:

```sh
docker compose stop web
unzip odds-backup-YYYYMMDD-HHMMSS.zip -d restore
docker compose cp restore/database.json web:/tmp/odds-database.json
docker compose cp restore/media/. web:/media/
docker compose start web
docker compose exec web python manage.py loaddata /tmp/odds-database.json
```

Verify archives with `unzip -t`, confirm `loaddata` completes, check `/health/`, then verify admin sign-in, employees and images. Backups include password hashes and personal employee data; restrict access and retain them securely. For an existing populated system, take a separate backup and restore into a clean target rather than loading duplicate records.

## Audit and troubleshooting

The audit trail records employee create/edit/deactivate/import, content changes, display/schedule changes and backups. Review it under **System settings & audit** or `/admin/`. View runtime output with `docker compose logs -f web`; check health at `http://SERVER:5175/health/`. Common startup problems are an unchanged example secret, a host missing from `DJANGO_ALLOWED_HOSTS`, an occupied port 5175 or unavailable media/database volume.

## Tests

Run checks and tests locally or in the running container:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test employees signage
```

Tests cover birthdays/leap-day rules, 600-row CSV import, XLSX parsing, role permissions, existing-record update safeguards, anniversaries, content expiry and category scheduling, device feeds, audit entries and backup archive integrity. Network-loss/PWA behavior should also be verified in the target kiosk browser and LAN environment before unattended production use.
