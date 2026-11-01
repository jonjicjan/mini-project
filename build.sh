#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.lock
python manage.py migrate --noinput
python manage.py collectstatic --noinput
