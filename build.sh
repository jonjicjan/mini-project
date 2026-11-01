#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install production dependencies
pip install -r requirements.lock

# Collect static files for WhiteNoise
python manage.py collectstatic --noinput

# Run database migrations
python manage.py migrate --noinput

# Bootstrap admin if credentials are provided in environment
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    python manage.py bootstrap_admin --if-missing
fi
