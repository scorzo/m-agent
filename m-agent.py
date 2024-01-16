import json
import pytz
from datetime import datetime
from openai import OpenAI
from calendar_package import list_events, add_calendar_event, update_or_cancel_event

# Read configuration file for API keys
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    openai_api_key = config['openai_api_key']
    timezone_config = config['timezone']

client = OpenAI(api_key=openai_api_key)

def provide_user_specific_recommendations(user_input):
    # Get current date in Los Angeles time zone
    my_timezone = pytz.timezone(timezone_config)
    my_time = datetime.now(my_timezone).strftime('%Y-%m-%d')
    messages = [
        {"role": "system", "content": f"You are a helpful AI.  You have the ability to schedule events in a Google Calendar. Assume today's date is {my_time} and timezone is {my_timezone}."},
        {"role": "user", "content": user_input}
    ]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0,
        functions=[
            {
                "name": "add_calendar_event",
                "description": "Add an event to Google Calendar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_summary": {"type": "string"},
                        "event_location": {"type": "string"},
                        "event_description": {"type": "string"},
                        "start_time": {"type": "string"},
                        "end_time": {"type": "string"},
                        "start_time_zone": {"type": "string"},
                        "end_time_zone": {"type": "string"},
                    },
                    "required": ["event_summary", "event_location", "event_description", "start_time", "end_time", "start_time_zone", "end_time_zone"],
                }
            },
            {
                "name": "list_events",
                "description": "List past and upcoming events from Google Calendar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {"type": "string"},
                        "max_results": {"type": "integer"},
                        "start_time": {"type": "string", "format": "date-time", "description": "Start time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)"},
                        "end_time": {"type": "string", "format": "date-time", "description": "End time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)"},
                        "timezone": {"type": "string", "description": "Timezone in which the start and end times are specified"}
                    },
                    "required": ["calendar_id", "max_results"],
                    "additionalProperties": True
                }
            },
            {
                "name": "update_or_cancel_event",
                "description": "Update or cancel an event in Google Calendar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {"type": "string"},
                        "event_id": {"type": "string"},
                        "update_body": {"type": "object"}
                    },
                    "required": ["calendar_id", "event_id"]
                }
            }
        ]
    )

    if response.choices[0].finish_reason == 'function_call':
        function_call = response.choices[0].message.function_call
        if function_call.name == "add_calendar_event":
            args = json.loads(function_call.arguments)
            return add_calendar_event(args['event_summary'], args['event_location'], args['event_description'], args['start_time'], args['end_time'], args['start_time_zone'], args['end_time_zone'])
        elif function_call.name == "list_events":
            args = json.loads(function_call.arguments)
            return list_events(
                calendar_id=args.get('calendar_id', 'primary'),
                max_results=args.get('max_results', 10),
                start_time=args.get('start_time'),  # If start_time is not provided, it defaults to None
                end_time=args.get('end_time'),      # If end_time is not provided, it defaults to None
                timezone=args.get('timezone', 'UTC')  # Default timezone set to 'UTC' if not provided
            )
        elif function_call.name == "update_or_cancel_event":
            args = json.loads(function_call.arguments)
            return update_or_cancel_event(args['calendar_id'], args['event_id'], args.get('update_body'))
    else:
        # Correctly access the content attribute of the ChatCompletionMessage object
        return response.choices[0].message.content

    return "I am sorry, but I could not understand your request."


if __name__ == "__main__":
    while True:
        user_input = input("Please enter your request (or type 'exit'): ")

        if user_input.lower() == 'exit':
            print("Exiting the program.")
            break

        output = provide_user_specific_recommendations(user_input)
        print(output)

