# README for Google Calendar Event Scheduling Script

## Overview:
This script integrates with Google Calendar using the Google Calendar API to schedule events. It utilizes OpenAI's GPT-3.5 for processing natural language inputs for scheduling requests.

## Setup and Usage

Install Required Libraries:

Ensure you have the Google API Client Library for Python installed.

    pip install --upgrade google-auth-oauthlib google-auth-httplib2 google-api-python-client

Install pytz timezone library:
    
    pip install pytz

Install OpenAI GPT-3.5:

    pip install openai

Execute the script: 

    python m-agent.py

The script interactively prompts for event scheduling commands (e.g., "Schedule a meeting with John on January 10 at 10 am") and processes these requests to add events to your Google Calendar.

Note: Ensure that you have the necessary permissions and correct calendar ID before running the script.