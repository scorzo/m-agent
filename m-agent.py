import json
import pytz
from datetime import datetime
import time
from openai import OpenAI
from calendar_package import list_events, add_calendar_event, update_or_cancel_event
from thread_store import store_thread, check_if_thread_exists

def read_config_file(file_path):
    """
    Reads a configuration file and extracts necessary information.

    :param file_path: The path to the configuration file.
    :return: A dictionary containing the configuration data.

    This function opens and reads a configuration file in JSON format. It extracts
    the OpenAI API key and the timezone configuration. If the file cannot be read,
    or if the required keys are not present, it raises an appropriate error.
    """
    try:
        with open(file_path, 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"The configuration file {file_path} was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The file {file_path} is not a valid JSON file.")

    openai_api_key = config.get('openai_api_key')
    timezone_config = config.get('timezone')

    if not openai_api_key or not timezone_config:
        raise ValueError("Required configuration keys ('openai_api_key', 'timezone') are missing.")

    return {'openai_api_key': openai_api_key, 'timezone': timezone_config}


config_data = read_config_file('config.json')
timezone_config = config_data['timezone']

openai_api_key = config_data['openai_api_key']
client = OpenAI(api_key=openai_api_key)


def get_chat_response(user_input, model="gpt-4-1106-preview"):
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content":"You are a helpful assistant."},
                {"role": "user", "content":user_input}
            ]
        )
        chat_response_text = completion.choices[0].message["content"]
        return chat_response_text

    except Exception as e:
        # API request exceptions
        return f"An error occurred: {str(e)}"

list_tools=[{"type":"function",
             "function":{
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
             }
             },
            {"type":"function",
             "function": {
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
             }
             },
            {"type":"function",
             "function":{
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
             },
            {"type":"function",
             "function":{
                 "name": "get_chat_response",
                 "description": "Provide chat responses to user queries",
                 "parameters": {
                     "type": "object",
                     "properties": {
                         "user_input": {"type": "string", "description": "User's query"},
                         "model": {"type": "string", "description": "GPT model to use"},
                     },
                     "required": ["user_input"]
                 }
             }
             }]

# define dispatch table
function_dispatch_table = {
    "add_calendar_event" : add_calendar_event,
    "list_events" : list_events,
    "update_or_cancel_event" : update_or_cancel_event,
    "get_chat_response" : get_chat_response
}


def create_or_retrieve_thread(user_input, lookup_id, client):
    """
    Creates a new thread or retrieves an existing one based on the lookup ID.
    Adds the user's input as a message to the thread.

    :param user_input: The input provided by the user.
    :param lookup_id: The lookup identifier for the thread.
    :param client: The client object for interacting with the API.
    :return: The thread object.
    """

    thread_id = check_if_thread_exists(lookup_id)
    thread = None

    if thread_id is None:
        thread = create_new_thread(lookup_id, client)
    else:
        thread = retrieve_existing_thread(thread_id, lookup_id, client)

    return thread

def create_new_thread(lookup_id, client):
    print(f"Creating new thread with lookupId {lookup_id}")
    try:
        thread = client.beta.threads.create()
        store_thread(lookup_id, thread.id)
        return thread
    except Exception as e:
        print(f"Failed to create new thread: {e}")
        return None

def retrieve_existing_thread(thread_id, lookup_id, client):
    print(f"Retrieving existing thread with lookupId {lookup_id}")
    try:
        return client.beta.threads.retrieve(thread_id)
    except Exception as e:
        print(f"Failed to retrieve existing thread ({thread_id}): {e}")
        return None

def add_message_to_thread(thread_id, user_input, client):
    try:
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )
    except Exception as e:
        print(f"Failed to add message to thread: {e}")


def create_and_run_assistant(thread, assistant_id=None, client=None, timezone_config=None):
    """
    Retrieves an existing assistant or creates a new one, and then runs it in the specified thread.

    :param thread: The thread object where the assistant will be run.
    :param assistant_id: The ID of an existing assistant (optional).
    :param client: The client object for interacting with the API.
    :param timezone_config: Timezone string (example: "America/Los_Angeles")
    :return: The run object.
    """
    try:
        assistant = retrieve_or_create_assistant(assistant_id, client, timezone_config)
        return create_run_for_assistant(thread.id, assistant.id, client)
    except Exception as e:
        print(f"Error in create_and_run_assistant: {e}")
        return None

def retrieve_or_create_assistant(assistant_id, client, timezone_config):
    my_time, my_timezone = get_current_time_and_timezone(timezone_config)
    if assistant_id:
        return client.beta.assistants.retrieve(assistant_id)
    else:
        return client.beta.assistants.create(
            name="ParallelFunction",
            instructions=f"You are a helpful AI. You have the ability to schedule events in Google Calendar. Assume today's date is {my_time} and timezone is {my_timezone}.",
            model="gpt-4-1106-preview",
            tools=list_tools
        )

def get_current_time_and_timezone(timezone_config):
    if not timezone_config:
        raise ValueError("Timezone configuration is not defined.")

    try:
        my_timezone = pytz.timezone(timezone_config)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"The provided timezone '{timezone_config}' is not recognized.")

    my_time = datetime.now(my_timezone).strftime('%Y-%m-%d')
    return my_time, my_timezone

def create_run_for_assistant(thread_id, assistant_id, client):
    return client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

def get_assistant_response(thread, run, client):
    """
    Monitors the status of an assistant's run and retrieves the response once completed.

    :param thread: The thread object associated with the run.
    :param run: The run object representing the assistant's execution.
    :param client: The client object for interacting with the OpenAI API.
    :return: The response from the completed run, if successful.

    The function performs the following actions:
    1. Continuously checks the status of the run in a loop.
    2. If the run is completed, it processes the completed run to retrieve the response.
    3. If the run requires additional action, it processes the required actions.
    4. If the run is still in progress, it waits for a specified time before rechecking.

    The function exits the loop and returns the response when the run is completed. In cases where the run requires
    action, it triggers appropriate processes to handle those actions. The function employs a delay between each status
    check to avoid overwhelming the server with requests.
    """
    while True:
        time.sleep(5)
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run_status.status == "completed":
            return process_completed_run(thread, client)

        elif run_status.status == "requires_action":
            process_required_action(run_status, thread, run, client)

        else:
            print("Waiting for the Assistant to process...")

def process_completed_run(thread, client):
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data:
        if msg.role == "assistant":
            print(f"Assistant: {msg.content[0].text.value}")
            return

def process_required_action(run_status, thread, run, client):
    required_actions = run_status.required_action.submit_tool_outputs.model_dump()
    tool_calls_output, tools_output = process_tool_calls(required_actions)

    print(f"{tool_calls_output}")
    submit_tool_outputs(thread, run, tools_output, client)

def process_tool_calls(required_actions):
    tool_calls_output = {'tool_calls': []}
    tools_output = []

    for action in required_actions["tool_calls"]:
        tool_call, tool_output = process_single_tool_call(action)
        tool_calls_output['tool_calls'].append(tool_call)
        tools_output.append(tool_output)

    return tool_calls_output, tools_output

def process_single_tool_call(action):
    func_name = action["function"]["name"]
    arguments = json.loads(action["function"]["arguments"]) if isinstance(action["function"]["arguments"], str) else action["function"]["arguments"]

    tool_call = {
        'id': action['id'],
        'function': {'arguments': arguments, 'name': func_name},
        'type': 'function'
    }

    func = function_dispatch_table.get(func_name)
    if func:
        result = func(**arguments)
        output = json.dumps(result) if not isinstance(result, str) else result
    else:
        print(f"Function {func_name} not found")
        output = None

    tool_output = {"tool_call_id": action["id"], "output": output} if output else None
    return tool_call, tool_output

def submit_tool_outputs(thread, run, tools_output, client):
    if tools_output:
        client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tools_output
        )

def process_user_request(user_input, thread_lookup_id, assistant_id=None, client=None, timezone_config=None):
    """
    Processes a user's request by creating a thread, running an assistant, and then retrieving the assistant's response.

    :param user_input: The input provided by the user.
    :param thread_lookup_id: The lookup identifier for the thread.
    :param assistant_id: The ID of an existing assistant (optional).
    :param client: The client object for interacting with the OpenAI API.
    :return: The response from the assistant or None if an error occurs.

    This function encapsulates the full process of handling a user request:
    1. Creating a thread (or retrieving an existing one) based on the 'thread_lookup_id'.
    2. Running an assistant within the thread.
    3. Retrieving the response from the assistant.

    If any step in the process fails, the function captures the exception, logs the error, and returns None.
    """
    try:
        thread = create_or_retrieve_thread(user_input, thread_lookup_id, client)
        if thread is None:
            raise Exception("Failed to create thread.")

        add_message_to_thread(thread.id, user_input, client)

        run = create_and_run_assistant(thread, assistant_id, client, timezone_config)
        if run is None:
            raise Exception("Failed to create and run assistant.")

        return get_assistant_response(thread, run, client)
    except Exception as e:
        print(f"Error in process_user_request: {e}")
        return None


def main():
    thread_lookup_id = 111
    assistant_id = None  # Replace with a valid assistant_id if needed

    while True:
        user_input = get_user_input()

        if user_input == 'exit':
            exit_program()

        process_user_request(user_input, thread_lookup_id, assistant_id, client, timezone_config)


def get_user_input():
    return input("Please enter your request (or type 'exit'): ").lower()

def exit_program():
    print("Exiting the program.")
    exit()

if __name__ == "__main__":
    main()

