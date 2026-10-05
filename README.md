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
