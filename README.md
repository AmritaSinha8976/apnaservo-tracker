# ApnaServo Team Tracker
Internal daily work-tracking and task app (Django). See SETUP_GUIDE.docx for step-by-step Mac + VS Code instructions.

Quick start:
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
Open http://127.0.0.1:8000/ and sign in as the superuser (it becomes the Admin).
Run tests: python manage.py test

## Render initial admin

For a new hosted database, create the first admin using temporary Render environment
variables: `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`,
`BOOTSTRAP_ADMIN_FULL_NAME`, and `BOOTSTRAP_ADMIN_PASSWORD`. Set all four, then use
this Render start command for the first deploy:

    python manage.py migrate && python manage.py bootstrap_admin && gunicorn config.wsgi:application --workers 2

After the service starts, remove all four `BOOTSTRAP_ADMIN_*` variables from Render.
The command is safe to run again: with no bootstrap values it skips setup, and it
does not change an admin account that already exists.
