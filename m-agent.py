import json
import pytz
from datetime import datetime
import time
from openai import OpenAI
from calendar_package import list_events, add_calendar_event, update_or_cancel_event

# Read configuration file for API keys
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    openai_api_key = config['openai_api_key']
    timezone_config = config['timezone']

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

def run_loop(thread_id, run_id):

    while True:
        # wait 5 seconds
        time.sleep(5)

        # retrieve run status
        run_status = client.beta.threads.runs.retrieve(
            thread_id = thread_id,
            run_id = run_id
        )

        # print(run.model_dump_json(indent=4))

        # if run is completed, get messages
        if run_status.status == "completed":
            messages = client.beta.threads.messages.list(
                thread_id = thread_id
            )

            # Reverse the messages list to start from the latest message
            for msg in messages.data:
                if msg.role == "assistant":
                    content = msg.content[0].text.value
                    print(f"Assistant: {content}")
                    return

        elif run_status.status == "requires_action":
            print("Requires action:")
            required_actions = run_status.required_action.submit_tool_outputs.model_dump()

            tool_calls_output = {'tool_calls': []}

            ### logging
            for action in required_actions["tool_calls"]:
                # Step 3: Extract the 'arguments' string
                arguments_str = action['function']['arguments']

                # Step 4: Convert the string representation to a dictionary
                arguments = json.loads(arguments_str)

                # Step 5: Use the dictionary in 'tool_calls_output'
                tool_call = {
                    'id': action['id'],
                    'function': {
                        'arguments': arguments,  # Now 'arguments' is a dictionary
                        'name': action['function']['name']
                    },
                    'type': 'function'
                }

                tool_calls_output['tool_calls'].append(tool_call)

            print(f"{tool_calls_output}")
            ### end logging

            tools_output = []

            for action in required_actions["tool_calls"]:
                func_name = action["function"]["name"]
                arguments = action["function"]["arguments"]

                # Check if arguments is a string, and convert it to a dictionary if it is
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)

                func = function_dispatch_table.get(func_name)
                if func:
                    result = func(**arguments)  # Step 3: Use the arguments in the function call
                    # ensure output is json string
                    output = json.dumps(result) if not isinstance(result, str) else result
                    tools_output.append({
                        "tool_call_id": action["id"],
                        "output": output
                    })
                else:
                    print(f"Function {func_name} not found")


            # submit the tool outputs to Assistants API
            client.beta.threads.runs.submit_tool_outputs(
                thread_id = thread_id,
                run_id = run_id,
                tool_outputs = tools_output
            )

        else:
            print("Waiting for the Assistant to process...")
            time.sleep(5)


def provide_user_specific_recommendations(user_input):
    # Get current date in Los Angeles time zone
    my_timezone = pytz.timezone(timezone_config)
    my_time = datetime.now(my_timezone).strftime('%Y-%m-%d')

    # step 1: create assistant
    assistant = client.beta.assistants.create(
        name="ParallelFunction",
        instructions= f"You are a helpful AI.  You have the ability to schedule events in Google Calendar. Assume today's date is {my_time} and timezone is {my_timezone}.",
        model="gpt-4-1106-preview",
        tools=list_tools
    )

    # step 2: create thread
    # Initialize or retrieve the thread ID (set to None if not existing)
    thread_id = None  # Replace this with code to retrieve the existing thread ID, if available
    thread_id = 'thread_1Mw6Ipvh74ak65qJWldCgdde'

    # Check if there is an existing thread ID, create a new thread if not
    if thread_id is None:
        thread = client.beta.threads.create()
        thread_id = thread.id  # Store this ID for future use


    message = client.beta.threads.messages.create(
        thread_id = thread_id,
        role="user",
        content = user_input
    )

    # step 3: run assistant
    run = client.beta.threads.runs.create(
        thread_id = thread_id,
        assistant_id = assistant.id
    )

    #print(run.model_dump_json(indent=4))


    run_loop(thread_id, run.id)





if __name__ == "__main__":
    while True:
        user_input = input("Please enter your request (or type 'exit'): ")

        if user_input.lower() == 'exit':
            print("Exiting the program.")
            break

        output = provide_user_specific_recommendations(user_input)
        #print(output)

