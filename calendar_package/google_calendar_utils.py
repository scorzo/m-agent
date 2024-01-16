import os
import pickle
from datetime import datetime, timedelta
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Scopes and OAuth 2.0 Credentials File
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'client_secret.json'
CALENDAR_ID = 'primary'  # or your calendar ID



def get_calendar_service():
    creds = None
    # Load the saved credentials if they exist
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no valid credentials, prompt the user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

# Initialize the Google Calendar API client using OAuth
service = get_calendar_service()



def format_event_time(event_time_str, timezone_str):
    # Parse the datetime string and convert it to the specified timezone
    event_time = datetime.fromisoformat(event_time_str)
    timezone = pytz.timezone(timezone_str)
    event_time = event_time.astimezone(timezone)

    # Format the datetime in the specified format
    return event_time.strftime('%A, %B %d at %I:%M%p') + f" ({timezone_str})"



def list_events(calendar_id='primary', max_results=10, start_time=None, end_time=None, timezone='UTC'):
    # Initialize timezone
    tz = pytz.timezone(timezone)

    # Set default times if not provided
    if start_time is None:
        start_time = datetime.now(tz).isoformat()
    else:
        start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=tz).isoformat()

    if end_time is None:
        end_time = (datetime.now(tz) + timedelta(days=7)).isoformat()
    else:
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=tz).isoformat()

    # Print what the function is querying
    print(f"Querying Google Calendar API for events in calendar '{calendar_id}' from '{start_time}' to '{end_time}' with a maximum of {max_results} results in timezone '{timezone}'.")

    try:
        events_result = service.events().list(calendarId=calendar_id, timeMin=start_time, timeMax=end_time,
                                              maxResults=max_results, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])
        if not events:
            return 'No events found in that time span.'

        event_details = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            start_formatted = format_event_time(start, event['start'].get('timeZone', timezone))
            end_formatted = format_event_time(end, event['end'].get('timeZone', timezone))
            print(f"{start_formatted} to {end_formatted} - {event['summary']}")

            event_details.append(f"{start} to {end} - {event['summary']}")

        return '\n'.join(event_details)
    except Exception as e:
        return f"An error occurred: {e}"



def add_calendar_event(event_summary, event_location, event_description, start_time, end_time, start_time_zone, end_time_zone):
    """
    Adds an event to the Google Calendar.
    """
    event = {
        'summary': event_summary,
        'location': event_location,
        'description': event_description,
        'start': {
            'dateTime': start_time,
            'timeZone': start_time_zone,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': end_time_zone,
        },
    }
    try:
        print(f"Created event '{event_summary}' at '{event_location}' starting from {start_time} to {end_time} in time zone {start_time_zone}.")
        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return f"Event created: {event_result.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred: {e}"

def update_or_cancel_event(calendar_id='primary', event_id=None, update_body=None):
    if update_body:
        try:
            updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=update_body).execute()
            return f"Event updated: {updated_event.get('htmlLink')}"
        except Exception as e:
            return f"An error occurred: {e}"

    else:
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return 'Event deleted.'
        except Exception as e:
            return f"An error occurred: {e}"


# Example usage
# list_events()
# create_event(summary='Flight to NYC', location='Airport', description='Flight details here')
# update_or_cancel_event(event_id='eventIdHere', update_body={'summary': 'Updated Event'})
