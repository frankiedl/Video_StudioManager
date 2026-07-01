"""Google Calendar sync.

Uses a single OAuth-connected Google account (the studio's calendar). When a
task has a due date and an assignee, an event is created/updated on that
calendar with the assignee's email as an attendee, so the deadline shows up
on the assignee's own Google Calendar via invite - no per-user login needed.
"""
import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .database import DATA_DIR

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_PATH = DATA_DIR / "google_credentials.json"
TOKEN_PATH = DATA_DIR / "google_token.json"


def has_client_credentials() -> bool:
    return CREDENTIALS_PATH.exists()


def is_connected() -> bool:
    return TOKEN_PATH.exists()


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def connect() -> None:
    """Runs the interactive OAuth consent flow in the user's browser (blocking)."""
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            "Falta data/google_credentials.json. Descárgalo desde Google Cloud "
            "Console (OAuth client ID de tipo 'Desktop app') y colócalo ahí."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())


def disconnect() -> None:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()


def _service():
    creds = _load_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


def upsert_task_event(task, assignee_email: str | None) -> str | None:
    """Creates or updates the calendar event for a task. Returns the event id."""
    service = _service()
    if not service or not task.due_date:
        return None

    start = task.start_date or task.due_date
    end = task.due_date
    if end <= start:
        end = start + datetime.timedelta(hours=1)

    body = {
        "summary": f"[Deadline] {task.title}",
        "description": task.description or "",
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        "reminders": {"useDefault": True},
    }
    if assignee_email:
        body["attendees"] = [{"email": assignee_email}]

    if task.gcal_event_id:
        try:
            event = service.events().update(
                calendarId="primary", eventId=task.gcal_event_id, body=body,
                sendUpdates="all",
            ).execute()
            return event["id"]
        except Exception:
            pass  # event may have been deleted on the Google side; fall through to create

    event = service.events().insert(
        calendarId="primary", body=body, sendUpdates="all"
    ).execute()
    return event["id"]


def delete_task_event(gcal_event_id: str) -> None:
    service = _service()
    if not service or not gcal_event_id:
        return
    try:
        service.events().delete(
            calendarId="primary", eventId=gcal_event_id, sendUpdates="all"
        ).execute()
    except Exception:
        pass
