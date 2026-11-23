#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py center_employee_photos
python manage.py ensure_default_admin
python manage.py collectstatic --noinput
exec gunicorn odds.wsgi:application --bind 0.0.0.0:5175 --workers 2 --access-logfile - --error-logfile -
