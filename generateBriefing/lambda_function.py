from __future__ import print_function
import datetime
import os
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google.generativeai as genai

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/tasks.readonly']

# ---------- Credential Management ----------
def get_credentials():
    """Retrieve Google API credentials from environment variables."""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing Google API credentials in environment variables")

    creds_data = {
        "token": None,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    }

    creds = Credentials.from_authorized_user_info(info=creds_data)

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds.valid:
        raise ValueError("Unable to refresh credentials")

    return creds

# ---------- Google API Functions ----------
def get_calendar_events(service, calendar_id, days_ahead=20):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + 'Z'

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        timeMax=future,
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    return events

def get_tasks(service, tasklist_id):
    tasks_response = service.tasks().list(tasklist=tasklist_id).execute()
    return tasks_response.get('items', [])

# ---------- Gemini API Integration ----------
def generate_summary(events, tasks):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""
    Here are the Google Calendar events and tasks.
    Provide a summary for the next 3 days, including today,
    with preparation tips. Consider undated tasks as always relevant.
    Today is {today_str}, I live in Berlin, and work on weekdays.
    Make educated guesses about events, consider the weather,
    and keep it concise with line breaks around 50 characters.
    """

    response = model.generate_content(prompt + str(events) + str(tasks))
    return response.text

# ---------- Lambda Handler ----------
def lambda_handler(event, context):
    creds = get_credentials()

    # Google Calendar
    calendar_service = build('calendar', 'v3', credentials=creds)
    events = get_calendar_events(calendar_service, os.getenv("CALENDAR_ID"))

    # Google Tasks
    tasks_service = build('tasks', 'v1', credentials=creds)
    tasks = get_tasks(tasks_service, os.getenv("TASKLIST"))

    # Generate Summary
    summary = generate_summary(events, tasks)
    return {
        'statusCode': 200,
        'body': summary
    }
