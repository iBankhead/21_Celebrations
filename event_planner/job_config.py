import json
import os

# Path to configuration file
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'job_settings.json')



# -------------------------------------------------------------
# Global configuration for job settings
# -------------------------------------------------------------
DEFAULT_JOB_CONFIG = {
    'check_overdue_tasks': {
        'enabled': False,
        'interval': 5,   # minutes
        'min': 1,
        'max': 60,
        'description': 'Checks overdue tasks every X minutes and updates their status.'
    },
    'send_reminder_email': {
        'enabled': False,
        'interval': 1,  # how often (in hours) to check for upcoming reminders
        'min': 1,
        'max': 24,
        'lead_time': 48,         # number of hours to sent reminder for due task
        'description': 'Sends reminder emails. The job checks every X hours; reminders are sent if tasks are due in lead time (hours) with a window duration (minutes).'
    },
    'send_invitation_email': {
        'enabled': False,
        'interval': 3,  # how often (in hours) to check for upcoming events
        'min': 1,
        'max': 24,
        'description': 'Sends invitation emails. The job checks every X hours; invitation is sent if event is upcoming and has date, time, and location set.'
    },
    'send_gift_search_invitation': {
        'enabled': False,
        'interval': 3,  # how often (in hours) to check for gift searches
        'min': 1,
        'max': 24,
        'description': 'Sends invitation emails. The job checks every X hours; invitation is sent if gift search is created and deadline is in the future.'
    },
    'gift_search_reminder': {
        'enabled': False,
        'interval': 1,  # how often (in hours) to check for upcoming reminders
        'min': 1,
        'max': 24,
        'lead_time': 48,         # number of hours to sent reminder for due task
        'description': 'Sends reminder emails. The job checks every X hours; reminders are sent if gift search ends in lead time (hours) with a window duration (minutes).'
    },
    'gift_search_results': {
        'enabled': False,
        'interval': 3,  # how often (in hours) to check for closed gift searches
        'min': 1,
        'max': 24,
        'description': 'Sends gift search result emails. The job checks every X hours; result is sent if gift search passed the deadline and users voted for proposals.'
    },
    'send_gift_contribution_invitation': {
        'enabled': False,
        'interval': 3,  # how often (in hours) to check for gift contributions
        'min': 1,
        'max': 24,
        'description': 'Sends invitation emails. The job checks every X hours; invitation is sent if gift contribution is created and deadline is in the future.'
    },
    'gift_contribution_reminder': {
        'enabled': False,
        'interval': 1,  # how often (in hours) to check for upcoming reminders
        'min': 1,
        'max': 24,
        'lead_time': 48,         # number of hours to sent reminder for due task
        'description': 'Sends reminder emails. The job checks every X hours; reminders are sent if gift contribution ends in lead time (hours) with a window duration (minutes).'
    },
    'store_user_scores': {
        'enabled': False,
        'interval': 12,  # hours
        'min': 1,
        'max': 24,
        'description': 'Stores user scores daily every X hours and updates historical data.',
        'rank_change_interval': 30,  # default interval in days for rank changes (past scores)
        'description2': 'Defines the comparison period for rank changes in the leaderboard.',
    },
    'create_birthday_event': {
        'enabled': False,
        'interval': 3,   # hours
        'min': 1,
        'max': 96,
        'min_users_required': 3,     # minimum number of honorees for upcoming birthdays required
        'max_users_allowed': 10,     # maximum number of honorees for upcoming birthdays allowed
        'future_search_offset': 30,   # check for birthdays days from now
        'description': 'Checks birthdays X days from now and creates an event when minimum number of honorees - not exceeding maximum number - is reached.'
    },
    'create_round_birthday_gift_search': {
        'enabled': False,
        'interval': 24,   # hours
        'min': 1,
        'max': 96,
        'future_search_offset': 30,   # check for round birthdays days from now
        'deadline': 7,   # set deadline before birthday
        'description': 'Checks round birthdays X days from now and creates a gift search which ends X days before the birthday. Sebds invitation email.'
    },
    'check_payment_reminder': {
        'enabled': False,
        'interval': 1,  # how often (in days) to check for upcoming reminders
        'min': 1,
        'max': 10,
        'overdue_threshold': 7,         # number of days to sent reminder after payment creation
        'description': 'Sends reminder emails. The job checks every X days; reminders are sent X days after payment was billed repeatedly according to interval.'
    },
    'update_event_status': {
        'enabled': False,
        'interval': 24,  # how often (in hours) to check for status changes
        'min': 1,
        'max': 96,
        'description': 'Checks the status of an event. The job checks every X hours; if time and place are fixed, event is past or all transactions paid, the status is changed.'
    },
    'update_contribution_status': {
        'enabled': False,
        'interval': 24,  # how often (in hours) to check for status changes
        'min': 1,
        'max': 96,
        'description': 'Checks the status of a gift contribution. The job checks every X hours; if status is "open" after deadline, the status is changed to "closed".'
    },
    'general': {
        'conversion_rate': 0.5,  # float
        'description': 'Conversion rate for payments in points (input as decimal number)',
        'payment_penalty': -25, # penalty for late payment (negative)
        'description2': 'Penalty for late payment in points (input as negative number)',
    },

}



# -------------------------------------------------------------
# Load global configuration for job settings from JSON file
# -------------------------------------------------------------
def load_job_config():
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
                return config
        except Exception as e:
            print("Error loading config file, using defaults:", e)
            return DEFAULT_JOB_CONFIG.copy()
    else:
        save_job_config(DEFAULT_JOB_CONFIG)
        return DEFAULT_JOB_CONFIG.copy()



# -------------------------------------------------------------
# Save global configuration for job settings to JSON file
# -------------------------------------------------------------
def save_job_config(config):
    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print("Error saving config file:", e)

# Initialize JOB_CONFIG at import time
JOB_CONFIG = load_job_config()