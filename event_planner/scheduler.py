import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from .jobs import check_overdue_tasks, send_reminder_email, store_user_scores, send_invitation_email,\
      create_birthday_event, gift_search_results, send_gift_search_invitation, gift_search_reminder,\
        create_round_birthday_gift_search, check_payment_reminder, update_event_status, send_gift_contribution_invitation,\
        gift_contribution_reminder, update_contribution_status
from event_planner.job_config import JOB_CONFIG



scheduler = BackgroundScheduler()

def schedule_jobs():
    # Remove all jobs if they exist
    for job in scheduler.get_jobs():
        print("Removed: ", job.id)    
        scheduler.remove_job(job.id)

    # Schedule job for overdue tasks
    if JOB_CONFIG['check_overdue_tasks']['enabled']:
        job = scheduler.add_job(
            check_overdue_tasks,
            trigger='interval',
            minutes=JOB_CONFIG['check_overdue_tasks']['interval'],
            id='check_overdue_tasks'
        )
        print("Started: ", job.id)

    # Schedule job for task becomimg overdue reminder
    if JOB_CONFIG['send_reminder_email']['enabled']:
        job = scheduler.add_job(
            send_reminder_email,
            trigger='interval',
            hours=JOB_CONFIG['send_reminder_email']['interval'],
            id='send_reminder_email'
        )
        print("Started: ", job.id)

    # Schedule job for event invitation email
    if JOB_CONFIG['send_invitation_email']['enabled']:
        job = scheduler.add_job(
            send_invitation_email,
            trigger='interval',
            hours=JOB_CONFIG['send_invitation_email']['interval'],
            id='send_invitation_email'
        )
        print("Started: ", job.id)

    # Schedule job for gift search invitation email
    if JOB_CONFIG['send_gift_search_invitation']['enabled']:
        job = scheduler.add_job(
            send_gift_search_invitation,
            trigger='interval',
            hours=JOB_CONFIG['send_gift_search_invitation']['interval'],
            id='send_gift_search_invitation'
        )
        print("Started: ", job.id)

    # Schedule job for gift search reminder
    if JOB_CONFIG['gift_search_reminder']['enabled']:
        job = scheduler.add_job(
            gift_search_reminder,
            trigger='interval',
            hours=JOB_CONFIG['gift_search_reminder']['interval'],
            id='gift_search_reminder'
        )
        print("Started: ", job.id)

    # Schedule job for gift search results email
    if JOB_CONFIG['gift_search_results']['enabled']:
        job = scheduler.add_job(
            gift_search_results,
            trigger='interval',
            hours=JOB_CONFIG['gift_search_results']['interval'],
            id='gift_search_results'
        )
        print("Started: ", job.id)

    # Schedule job for gift contribution invitation email
    if JOB_CONFIG['send_gift_contribution_invitation']['enabled']:
        job = scheduler.add_job(
            send_gift_contribution_invitation,
            trigger='interval',
            hours=JOB_CONFIG['send_gift_contribution_invitation']['interval'],
            id='send_gift_contribution_invitation'
        )
        print("Started: ", job.id)

    # Schedule job for gift contribution reminder
    if JOB_CONFIG['gift_contribution_reminder']['enabled']:
        job = scheduler.add_job(
            gift_contribution_reminder,
            trigger='interval',
            hours=JOB_CONFIG['gift_contribution_reminder']['interval'],
            id='gift_contribution_reminder'
        )
        print("Started: ", job.id)

    # Schedule job for birthday event
    if JOB_CONFIG['create_birthday_event']['enabled']:
        job = scheduler.add_job(
            create_birthday_event,
            trigger='interval',
            hours=JOB_CONFIG['create_birthday_event']['interval'],
            id='create_birthday_event'
        )
        print("Started: ", job.id)

    # Schedule job for birthday gift search
    if JOB_CONFIG['create_round_birthday_gift_search']['enabled']:
        job = scheduler.add_job(
            create_round_birthday_gift_search,
            trigger='interval',
            hours=JOB_CONFIG['create_round_birthday_gift_search']['interval'],
            id='create_round_birthday_gift_search'
        )
        print("Started: ", job.id)

    # Schedule job for payment overdue reminder
    if JOB_CONFIG['check_payment_reminder']['enabled']:
        job = scheduler.add_job(
            check_payment_reminder,
            trigger='interval',
            days=JOB_CONFIG['check_payment_reminder']['interval'],   # days
            id='check_payment_reminder'
        )
        print("Started: ", job.id)

    # Schedule job for historical data
    if JOB_CONFIG['store_user_scores']['enabled']:
        job = scheduler.add_job(
            store_user_scores,
            trigger='interval',
            hours=JOB_CONFIG['store_user_scores']['interval'],
            id='store_user_scores'
        )
        print("Started: ", job.id)

    # Schedule job for event status changes
    if JOB_CONFIG['update_event_status']['enabled']:
        job = scheduler.add_job(
            update_event_status,
            trigger='interval',
            hours=JOB_CONFIG['update_event_status']['interval'],  # hours
            id='update_event_status'
        )
        print("Started: ", job.id)

    # Schedule job for event status changes
    if JOB_CONFIG['update_contribution_status']['enabled']:
        job = scheduler.add_job(
            update_contribution_status,
            trigger='interval',
            hours=JOB_CONFIG['update_contribution_status']['interval'],  # hours
            id='update_contribution_status'
        )
        print("Started: ", job.id)

# Initial scheduling
schedule_jobs()

# Start scheduler, module-level flag to prevent double-starting
if not hasattr(scheduler, '_has_been_started'):
    scheduler.start()
    scheduler._has_been_started = True

# Shut down scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


