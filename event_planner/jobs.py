import random
from collections import defaultdict
from django.db.models import Sum, Count
from datetime import date
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from event_planner.job_config import JOB_CONFIG
from .models import *




# -------------------------------------------------------------
# Generate calender item
# -------------------------------------------------------------
def generate_ics_for_event(event, points):
    event_date_time = datetime.combine(event.date, event.time)
    event_start = event_date_time.strftime("%Y%m%dT%H%M%SZ")
    event_end = (event_date_time + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
    timestamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    ics = f"""BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//21Celebrations//Event//EN
        BEGIN:VEVENT
        UID:{event.id}@{settings.SITE_ID}
        DTSTAMP:{timestamp}
        DTSTART:{event_start}
        DTEND:{event_end}
        SUMMARY:{event.title}
        LOCATION:{event.location}
        DESCRIPTION:Invitation to attend {event.description}. Attendance awards {points} points.
        END:VEVENT
        END:VCALENDAR
        """
    return ics



# -------------------------------------------------------------
# Checks if task is overdue, sets status (not for completed tasks), and sends mail to all responsible users
# -------------------------------------------------------------
def check_overdue_tasks():
    now = timezone.localtime(timezone.now())
    print("Overdue job runs at" , now)
    # Query tasks that are overdue (due_date < now), not completed and not already marked as overdue
    tasks_overdue = Task.objects.filter(due_date__lt=now).exclude(status__in=['completed', 'overdue'])
    
    for task in tasks_overdue:
        task.status = 'overdue'
        task.save()

        # Get all assigned users
        assigned_users = list(task.assigned_to.all())

        # For each assigned user, send email notification
        for user in assigned_users:
            # Update task status to 'overdue'
            current_score = user.total_score
            # Calculate potential new score if task is completed (gaining base_points) or if failure persists (losing penalty_points)
            base_points = task.base_points or 0
            penalty_points = task.penalty_points or 0
            new_score_if_success = current_score + base_points 
            
            # Find closest competitor above and below in the leaderboard
            competitor_above = UserProfile.objects.filter(total_score__gt=current_score).order_by('total_score').first()
            competitor_below = UserProfile.objects.filter(total_score__lt=current_score).order_by('-total_score').first()

            # Build ranking comparison message based on the user's total_score
            ranking_message = ""
            if competitor_below and current_score < competitor_below.total_score and current_score + penalty_points >= competitor_below.total_score:
                ranking_message += (
                    f"As you have not completed the task on time, you will fall behind {competitor_below.user.username} on the leaderboard.\n"
                )
            if competitor_above and new_score_if_success > competitor_above.total_score:
                ranking_message += (
                    f"If you complete the task, you still can overtake {competitor_above.user.username} on the leaderboard.\n"
                )
            if not ranking_message:
                ranking_message = "No significant change in your ranking is expected, but every effort counts – keep up the great work!!\n"

            # Build the email message
            message = (
                f"Dear {user.user.username},\n\n"
                f"This is to inform you that the task '{task.title}', due on {task.due_date}, is now overdue.\n\n"
                "Penalty points have been irreversibly deducted from your score.\n"
                "However, completing the task can still earn you points awarded.\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
                f"{ranking_message}\n"
            )
            
            # Send the email (assumes the related User object holds the email at user.user.email)
            send_mail(
                subject=f"Task '{task.title}' is overdue",
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.user.email],
            )


# -------------------------------------------------------------
# Sends mail in a timeframe before task gets overdue to all responsible users
# -------------------------------------------------------------
def send_reminder_email():
    now = timezone.localtime(timezone.now())
    print("Reminder job runs at" , now)

    # Use configured lead time and window duration
    config = JOB_CONFIG['send_reminder_email']
    # Hours before due date to send reminder
    lead_time = config.get('lead_time', 1)       
    # Calculate target reminder time
    reminder_time = now + timedelta(hours=lead_time)
    # Time window to catch tasks due 1 to 96 hours away
    window_start = reminder_time
    window_duration = lead_time * 60  # window in minutes
    window_end = reminder_time + timedelta(minutes=window_duration)

    # Query tasks due in window that have not had a reminder sent and are not completed
    tasks_remind = Task.objects.filter(
        due_date__gte=window_start,
        due_date__lt=window_end,
    ).exclude(status__in=['completed', 'reminder_sent'])
    
    # Iterate over tasks approaching deadline
    for task in tasks_remind:
        # Construct URL to dashboard
        if settings.DEBUG:
            index_url = "http://127.0.0.1:8000" + "/index.html"
        else:
            index_url = getattr(settings, "SITE_URL", "http://21celebrations.com") + "/index.html"

        # Get points assigned to the task
        base_points = task.base_points or 0
        penalty_points = task.penalty_points or 0

        # Get all assigned users
        assigned_users = list(task.assigned_to.all())

        # Iterate over users responsible for the task
        for user in assigned_users:
            # Create a list of other users' usernames (excluding the current recipient)
            other_usernames = [u.user.username for u in assigned_users if u.pk != user.pk]
            if other_usernames:
                others_str = "Together with " + ", ".join(other_usernames) + ", you are responsible for completing this task. "
            else:
                others_str = ""

            current_score = user.total_score
            # Compute potential scores after task completion or failure
            new_score_if_success = current_score + base_points
            new_score_if_failure = current_score - penalty_points
            # Find the closest competitor above (with a higher score)
            competitor_above = UserProfile.objects.filter(total_score__gt=current_score).order_by('total_score').first()
            # Find the closest competitor below (with a lower score)
            competitor_below = UserProfile.objects.filter(total_score__lt=current_score).order_by('-total_score').first()
            # Determine what ranking change might occur
            ranking_message = ""
            if competitor_above and new_score_if_success > competitor_above.total_score:
                ranking_message += (
                    f"If you complete this task, you'll overtake "
                    f"{competitor_above.user.username} on the leaderboard.\n"
                )
            if competitor_below and new_score_if_failure < competitor_below.total_score:
                ranking_message += (
                    f"If you fail to complete this task on time, you might fall behind "
                    f"{competitor_below.user.username} on the leaderboard.\n"
                )
            if not ranking_message:
                ranking_message = "No change in your rank is expected, but every task counts – keep up the great work!\n"

            subject = f"Reminder: Task '{task.title}' is due soon"
            message = (
                f"Dear {user.user.username},\n\n"
                f"This is a reminder that the task '{task.title}' is due on {task.due_date}.\n\n"
                f"{others_str}\n\n"
                f"Please ensure you complete it on time.\n\n"
                f"You can change the status of the task by visiting {index_url}. On completion you will receive {base_points} points. "
                f"If the task is not completed on time, {penalty_points} penalty points will be deducted "
                f"(note: penalty points can no longer be cancelled once they have been deducted).\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
                f"{ranking_message}"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [user.user.email])

        # Mark task as reminder sent to avoid sending duplicate reminders
        task.status = 'reminder'
        task.save()



# -------------------------------------------------------------
# Sends invitation mail to all active users when date, time, and location of event are set
# -------------------------------------------------------------
def send_invitation_email():
    now = timezone.localtime(timezone.now())
    print("Invitation job runs at" , now)
    # Use configured lead time and window duration
    config = JOB_CONFIG['send_reminder_email']
    # Query events that have date, time, and location set, and that are upcoming
    events = Event.objects.filter(
        date__isnull=False,
        time__isnull=False,
        location__isnull=False,
        date__gte=now.date(),
        invitation_sent=False
    )
    
    for event in events:
        # For each event, send invitation email to all active users
        profiles = UserProfile.objects.filter(is_inactive=False)
        
        # Construct URL to dashboard
        if settings.DEBUG:
            site_url = "http://127.0.0.1:8000"
        else:
            site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

        attend_url = site_url + reverse('attend_from_mail', args=[event.id])

        # Retrieve points for role from the RoleConfiguration model
        config = RoleConfiguration.objects.filter(role='attendee').first()
        attendance_points = config.points if config else 0

        for profile in profiles:
            user = profile.user

            # Calculate new score of user when he attends
            current_score = profile.total_score
            new_score = current_score + attendance_points

            # Leaderboard comparison: get next user with higher score, and next with lower score
            competitor_above = UserProfile.objects.filter(total_score__gt=current_score).order_by('total_score').first()
            competitor_below = UserProfile.objects.filter(total_score__lt=current_score).order_by('-total_score').first()

            ranking_message = ""
            if competitor_above and new_score > competitor_above.total_score:
                ranking_message += f"By attending, you'll overtake {competitor_above.user.username} on the leaderboard. "
            if competitor_below and new_score < competitor_below.total_score:
                ranking_message += f"If you don't attend, you risk falling behind {competitor_below.user.username} on the leaderboard. "
            if not ranking_message:
                ranking_message = "Your ranking remains stable, but every point counts!"

            # Prepare email content using HTML template
            context = {
                'user': user,
                'event': event,
                'attendance_points': attendance_points,
                'ranking_message': ranking_message,
                'attend_url': attend_url,
            }
            html_content = render_to_string("email/invitation_email.html", context)
            text_content = strip_tags(html_content)
            subject = f"Invitation: {event.title} on {event.date}"
            msg = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
            msg.attach_alternative(html_content, "text/html")
            
            # Attach Outlook-compatible ICS file
            ics_content = generate_ics_for_event(event, attendance_points)
            msg.attach("event.ics", ics_content, "text/calendar")
            msg.send()
        
        # Mark the event as having sent invitations
        event.invitation_sent = True
        event.save()



# -------------------------------------------------------------
# Sends mail with invitation to propose and vote on gifts when search is created (except donee)
# -------------------------------------------------------------
def send_gift_search_invitation():
    now = timezone.localtime(timezone.now())
    print("Gift invitation job runs at" , now)

    # Find gift searches that have not been processed
    today = now.date()
    gift_searches = GiftSearch.objects.filter( deadline__gte=today, final_results_sent=False, invitation_sent=False)
    if not gift_searches.exists():
        return

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    # Get points for proposal
    config_proposer = GiftConfiguration.objects.filter(role='proposer').first()
    points_proposer = config_proposer.points if config_proposer else 0

    # Get points for voting
    config_voter = GiftConfiguration.objects.filter(role='voter').first()
    points_voter = config_voter.points if config_voter else 0

    # Get points for winning
    config_winner = GiftConfiguration.objects.filter(role='winner').first()
    points_winner = config_winner.points if config_winner else 0

    # Build points details message
    points_message = (
        "Points available for participating:\n"
        f"- Propose a gift: {points_proposer} points\n"
        f"- Vote on proposals: {points_voter} points\n"
        f"- Winning the gift search: {points_winner} points\n\n"
    )

    for gs in gift_searches:
        # Construct link to view gift search details
        gift_url = site_url + reverse("gift_search_detail", args=[gs.id])
        
        # Get all active users except donee
        active_users = UserProfile.objects.filter(is_inactive=False).exclude(pk=gs.donee.pk)
        
        # Compose email message
        for profile in active_users:
            subject = f"New Gift Search: {gs.title}"
            message = (
                f"Dear {profile.user.username},\n\n"
                f"A new gift search '{gs.title}' has been created.\n"
                f"Donee: {gs.donee.user.username}\n"
                f"Purpose: {gs.purpose}\n\n"
                "We invite you to propose a suitable gift for the donee and to vote on proposals.\n"
                "By participating, you will earn points for your contributions!\n"
                f"{points_message}"
                f"Please note, the deadline for proposals and votes is: {gs.deadline}.\n\n"
                f"View the details here: {gift_url}\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [profile.user.email])
        
        # Mark gift search as processed
        gs.invitation_sent = True
        gs.save()



# -------------------------------------------------------------
# Sends mail with invitation to contribute for gifts when contribution is created (except donee)
# -------------------------------------------------------------
def send_gift_contribution_invitation():
    now = timezone.localtime(timezone.now())
    print("Contribution invitation job runs at" , now)
    
    # Find gift contributions that have not been processed
    today = now.date()
    gift_contributions = GiftContribution.objects.filter(deadline__gte=today, status='open', invitation_sent=False)
    if not gift_contributions.exists():
        return

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    # Get conversion rate from job settings
    conversion_rate = JOB_CONFIG.get('general', {}).get('conversion_rate', 0.5)
    
    for gc in gift_contributions:
        # Construct link to view gift contribution
        gift_url = site_url + reverse("gift_contribution_list")
        
        # Get all active user profiles except donee
        active_users = UserProfile.objects.filter(is_inactive=False).exclude(pk=gc.donee.pk)
        
        # Compose email message
        for profile in active_users:
            subject = f"Invitation: Contribute to '{gc.title}'"
            message = (
                f"Dear {profile.user.username},\n\n"
                f"A new gift contribution opportunity has been created:\n\n"
                f"Title: {gc.title}\n"
                f"Description: {gc.description}\n"
                f"Deadline: {gc.deadline}\n"
                f"Collection Target: {gc.collection_target}\n"
                f"Manager: {gc.manager.user.username}\n\n"
                "You are invited to make a monetary contribution.\n"
                f"Your contributions will be recognized with points at a conversion rate of {conversion_rate}.\n"
                "This means the more you contribute, the more points you will earn.\n\n"
                "Please note: All contributions must be paid to the manager once the contribution period ends.\n\n"
                f"View full details here: {gift_url}\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [profile.user.email])
        
        # Mark gift contribution as processed
        gc.invitation_sent = True
        gc.save()



# -------------------------------------------------------------
# Sends mail in a timeframe before gift search expires to all active users (except donee)
# -------------------------------------------------------------
def gift_search_reminder():
    now = timezone.localtime(timezone.now())
    print("Gift search reminder job runs at", now)
    today = timezone.now().date()

    # Use configured lead time and window duration
    config = JOB_CONFIG['gift_search_reminder']
    # Hours before deadline to send reminder
    lead_time = config.get('lead_time', 1)       
    # Calculate target reminder time
    reminder_time = now + timedelta(hours=lead_time)
    # Time window to deadline due 1 to 48 hours away
    window_start = reminder_time
    window_duration = lead_time * 60  # window in minutes
    window_end = reminder_time + timedelta(minutes=window_duration)
    
    # Find active gift searches closing in window (deadline not passed, not final, no reminder sent yet)
    gift_searches = GiftSearch.objects.filter(
        deadline__gte=window_start,
        deadline__lt=window_end,
        final_results_sent=False,
        invitation_sent = True,
        reminder_sent=False
    )
    if not gift_searches.exists():
        return

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    for gs in gift_searches:
        # Get proposals for this gift search
        gs_query = GiftProposal.objects.filter(gift_search=gs)
        if gs_query.exists():
            proposals = list(gs_query)
            # Sort the list 
            sorted_proposals = sorted(proposals, key=lambda proposal: proposal.votes.count(), reverse=True)
            rank = 0
            proposals_summary = ""
            for proposal in sorted_proposals:
                rank += 1
                proposals_summary += f"{rank}. {proposal.title}: {proposal.votes.count()} votes\n"

        # Construct link to view gift search details
        gift_url = site_url + reverse("gift_search_detail", args=[gs.id])

        # Get all active users except the donee
        active_users = UserProfile.objects.filter(is_inactive=False).exclude(pk=gs.donee.pk)

        for profile in active_users:
            subject = f"Reminder: Gift Search '{gs.title}' is Still Active"
            message = (
                f"Dear {profile.user.username},\n\n"
                f"A reminder for the gift search '{gs.title}' has been sent.\n"
                f"Donee: {gs.donee.user.username}\n"
                f"Purpose: {gs.purpose}\n"
                f"Deadline for proposals: {gs.deadline}\n\n"
                "Current proposals:\n"
                f"{proposals_summary}\n"
                "We invite you to vote on these proposals or submit your own gift idea.\n\n"
                f"View the gift search details here: {gift_url}\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [profile.user.email])
        
        # Mark this gift search as processed again
        gs.reminder_sent = True
        gs.save()



# -------------------------------------------------------------
# Sends mail in a timeframe before gift contribution expires to all active users (except donee)
# -------------------------------------------------------------
def gift_contribution_reminder():
    now = timezone.localtime(timezone.now())
    print("Gift contribution reminder job runs at", now)
    today = timezone.now().date()

    # Use configured lead time and window duration
    config = JOB_CONFIG['gift_contribution_reminder']
    # Hours before deadline to send reminder
    lead_time = config.get('lead_time', 1)       
    # Calculate target reminder time
    reminder_time = now + timedelta(hours=lead_time)
    # Time window to deadline due 1 to 48 hours away
    window_start = reminder_time
    window_duration = lead_time * 60  # window in minutes
    window_end = reminder_time + timedelta(minutes=window_duration)

    # Find active gift contributions closing in window (deadline not passed, not final, no reminder sent yet)
    gift_contributions = GiftContribution.objects.filter(
        deadline__gte=window_start,
        deadline__lt=window_end,
        status='open',
        invitation_sent = True,
        reminder_sent=False
    )
    if not gift_contributions.exists():
        return

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    # Get conversion rate from job settings
    conversion_rate = JOB_CONFIG.get('general', {}).get('conversion_rate', 1)
    
    for gc in gift_contributions:
        # Build link to view gift contributions
        gift_url = site_url + reverse("gift_contribution_list")
        
        # Get all active users (is_inactive=False) except the donee
        active_users = UserProfile.objects.filter(is_inactive=False).exclude(pk=gc.donee.pk)
        
        for profile in active_users:
            # Skip users who have already contributed
            if gc.contributions.filter(contributor=profile).exists():
                continue

            subject = f"Reminder: Contribute to '{gc.title}' is Still Active"
            message = (
                f"Dear {profile.user.username},\n\n"
                f"A reminder for the gift contribution '{gc.title}' has been issued.\n\n"
                f"Purpose: {gc.description}\n"
                f"Deadline: {gc.deadline}\n"
                f"Manager: {gc.manager.user.username}\n\n"
                "We invite you to contribute by making a monetary contribution. "
                f"Your contributions will be recognized with points at a conversion rate of {conversion_rate}. "
                "This means the more you contribute, the more points you will earn.\n\n"
                "Please note: The deadline is coming nearer. All contributions must be paid to the manager "
                "once the contribution period ends.\n\n"
                f"View full details here: {gift_url}\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [profile.user.email])
        
        # Mark this gift search as processed again
        gc.reminder_sent = True
        gc.save()



# -------------------------------------------------------------
# Sends mail with announcement of winner and winning gift proposal (except donee)
# -------------------------------------------------------------
def gift_search_results():
    now = timezone.localtime(timezone.now())
    print("Gift results job runs at" , now)
    today = timezone.now().date()
    
    # Find gift searches whose deadline has passed and have not been processed
    gift_searches = GiftSearch.objects.filter(deadline__lt=today, final_results_sent=False)
    if not gift_searches.exists():
        return

    # Construct URL to results
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    # Construct link to view closed searches
    gift_url = site_url + reverse("closed_gift_list")

    for gs in gift_searches:
        # Get top 3 proposals ordered by vote count
        gs_query = GiftProposal.objects.filter(gift_search=gs)
        if gs_query.exists():
            proposals = list(gs_query)
           # Sort the list 
            sorted_proposals = sorted(proposals, key=lambda proposal: proposal.votes.count(), reverse=True)
            rank = 0
            proposals_summary = ""
            for proposal in sorted_proposals[:3]:
                rank += 1
                proposals_summary += f"{rank}. {proposal.title}: {proposal.votes.count()} votes\n"
                if rank == 1:
                    winner_proposal = proposal
        else:
            # No proposals found
            gs.final_results_sent = True
            gs.save()
            continue

        # Get all active users except donee
        active_users = UserProfile.objects.filter(is_inactive=False).exclude(pk=gs.donee.pk)

        for profile in active_users:
            # Check if user is proposer for top proposals
            user_message = ""
            for proposal in proposals:
                if proposal.proposed_by == profile and proposal == winner_proposal:
                    # Get points awarded from role configuration
                    config = GiftConfiguration.objects.filter(role='winner').first()
                    points_awarded = config.points if config else 0
                    user_message = (f"Congratulations! Your proposal '{proposal.title}' received {proposal.votes.count()} votes "
                                        f"and you were awarded {points_awarded} points.\n")
                    break

            # Check if user has voted for proposals
            aggregate = GiftScoreHistory.objects.filter(user_profile=profile, score_type='vote').aggregate(total=Sum('points_change'))
            total = aggregate['total'] if aggregate['total'] is not None else 0
            if total > 0:
                user_message += (f"For your votes on proposals you earned {total} points. ")

            # Check if user has proposed gifts
            aggregate = GiftScoreHistory.objects.filter(user_profile=profile, score_type='proposal').aggregate(total=Sum('points_change'))
            total = aggregate['total'] if aggregate['total'] is not None else 0
            if total > 0:
                user_message += (f"For your proposals in this gift search you earned {total} points. ")

            # Construct mail
            subject = f"Gift Search Results: {gs.title}"
            message = (
                f"Dear {profile.user.username},\n\n"
                f"The gift search '{gs.title}' has concluded.\n\n"
                f"Top proposals:\n{proposals_summary}\n"
                f"{user_message}"
                f"You can view the results here: {gift_url}\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
            )
            # Send email
            send_mail(subject, message, settings.EMAIL_HOST_USER, [profile.user.email])
        
        # Mark gift search as processed
        gs.final_results_sent = True
        gs.save()



# -------------------------------------------------------------
# Stores user's scores once a day in the score history
# -------------------------------------------------------------
def store_user_scores():
    now = timezone.localtime(timezone.now())
    print("PastScore job runs at" , now)
    today = timezone.now().date()
    config = JOB_CONFIG['store_user_scores']

    # Iterate over all user profiles
    for profile in UserProfile.objects.all():
        # Store today's scores in PastUserScores
        try:
            past_score = PastUserScores.objects.get(user=profile.user, score_date=today)
            # Update with current scores
            past_score.total_score = profile.total_score
            past_score.task_score = profile.task_score
            past_score.role_score = profile.role_score
            past_score.gift_score = profile.gift_score
            past_score.payment_score = profile.payment_score
            past_score.save()
        except PastUserScores.DoesNotExist:
            # Create record for today if it doesn't exist
            PastUserScores.objects.create(
                user=profile.user,
                score_date=today,
                total_score=profile.total_score,
                task_score=profile.task_score,
                role_score=profile.role_score,
                gift_score=profile.gift_score,
                payment_score=profile.payment_score,
            )

        # Use configured interval in days
        rank_interval = config.get('rank_change_interval', 30)
        # Update UserProfile past fields using record from X days ago
        days_ago = today - timedelta(days=rank_interval)
        try:
            past_record = PastUserScores.objects.get(user=profile.user, score_date=days_ago)
            # Write scores into the _past fields of profile
            profile.task_score_past = past_record.task_score
            profile.role_score_past = past_record.role_score
            profile.gift_score_past = past_record.gift_score
            profile.payment_score_past = past_record.payment_score
            profile.save()
        except PastUserScores.DoesNotExist:
            # If no record is found, do nothing
            pass



# -------------------------------------------------------------
# Creates birthday event when number of honorees is reached and sends email
# -------------------------------------------------------------
def create_birthday_event():
    now = timezone.localtime(timezone.now())
    print("Birtday job runs at" , now)

    # Use configured number for honorees and days for planning
    config = JOB_CONFIG['send_reminder_email']
    future_search_offset = config.get('future_search_offset', 30)  # start searching defined days from now
    min_users_required = config.get('min_users_required', 3)    # threshold for triggering event creation
    max_users_allowed = config.get('max_users_allowed', 10)    

    today = timezone.localtime(timezone.now()).date()
    first = date(today.year, 1, 1)
    last = date(today.year, 12, 31)

    # Only consider active users with a birthday defined
    profiles = UserProfile.objects.filter(is_inactive=False, birthday__isnull=False)
    
    # Prepare candidate list: determine each user's next birthday date
    candidates = []
    for profile in profiles:
        birthday_this_year = profile.birthday.replace(year=today.year)
        candidates.append((birthday_this_year, profile))

        # If birthday already occurred this year, use next year's birthday as well
        if birthday_this_year < today:
            birthday_next_year = profile.birthday.replace(year=today.year + 1)
            candidates.append((birthday_next_year, profile))

    # Partition candidates into past and future groups
    past_group = [(b, p) for (b, p) in candidates if b < today]
    future_group = [(b, p) for (b, p) in candidates if b >= today]

    # Exclude users who have already been honouree in birthday event this year
    def not_already_honoree(profile):
        return not EventParticipant.objects.filter(
            user_profile=profile,
            event__event_type="birthday",
            #event__date__year=today.year,
            joined_at__gte=first,
            joined_at__lte=last,
            role="honouree"
        ).exists()
    
    past_group = [(b, p) for (b, p) in past_group if not_already_honoree(p)]
    future_group = [(b, p) for (b, p) in future_group if not_already_honoree(p)]

    # Start with candidates from past group, sorted by birthday
    selected = sorted(past_group, key=lambda tup: tup[0])
    
    # If below minimum, add candidates from future, but only those with birthday <= (today + future_search_offset)
    if len(selected) < min_users_required:
        future_date = today + timedelta(days=future_search_offset)
        future_candidates = [ (b, p) for (b, p) in future_group if b <= future_date ]
        future_candidates.sort(key=lambda tup: tup[0])
        for tup in future_candidates:
            selected.append(tup)
            if len(selected) >= max_users_allowed:
                break

    # If still below minimum threshold, exit
    if len(selected) < min_users_required:
        return

    # If any future candidates were included, add all additional future candidates whose birthday month matches that of last candidate from future portion
    future_in_selected = [ (b, p) for (b, p) in selected if b >= today ]
    if future_in_selected:
        last_future_birthday, _ = future_in_selected[-1]
        target_month = last_future_birthday.month
        for (b, p) in future_group:
            if b.month == target_month and (b, p) not in selected:
                selected.append((b, p))

    # Trim the candidate list if it exceeds max_users_allowed
    if len(selected) > max_users_allowed:
        selected = sorted(selected, key=lambda tup: tup[0])[:max_users_allowed]
    
    # Final check: if final candidate count is below the minimum threshold, exit
    if len(selected) < min_users_required:
        return

    honoree_profiles = [p for (b, p) in selected]

    # Choose one candidate randomly to be event manager
    manager_profile = random.choice(honoree_profiles)
    
    # Create event
    honoree_names = [p.user.username for p in honoree_profiles]
    event_title = "Birthday Celebration for " + ", ".join(honoree_names)
    event_description = (
        "We celebration our birthday with you.\n"
        "Honorees: " + ", ".join(honoree_names)
    )
    event = Event.objects.create(
        title=event_title,
        description=event_description,
        is_auto_generated=True,
        status="pending",
        event_type="birthday"
    )
    
    # Create event participants
    for profile in honoree_profiles:
        role = "honouree"
        EventParticipant.objects.create(event=event, user_profile=profile, role=role)
        if profile == manager_profile:
            role = "manager"
            EventParticipant.objects.create(event=event, user_profile=profile, role=role)
    
    # Construct event URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    event_url = site_url + reverse("edit_event_detail", args=[event.id])

    # Send personalized emails
    subject = "Birthday Celebration Event Created!"
    for profile in honoree_profiles:
        recipient_email = profile.user.email
        if profile == manager_profile:
            message = (
                f"Dear {profile.user.username},\n\n"
                "Congratulations! You have been selected as the event manager for the upcoming birthday celebration event.\n\n"
                "Honorees:\n" + "\n".join(honoree_names) + "\n\n"
                "Please check the event details and plan the party accordingly.\n"
                "You can view the event here: " + event_url + "\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
            )
        else:
            message = (
                f"Dear {profile.user.username},\n\n"
                "An automated birthday celebration event has been created because we have enough upcoming birthdays.\n\n"
                "Honorees:\n" + "\n".join(honoree_names) + "\n\n"
                f"The event manager is {manager_profile.user.username}.\n\n"
                "Please check the event details and help plan a party.\n"
                "You can view the event here: " + event_url + "\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
            )
        send_mail(subject, message, settings.EMAIL_HOST_USER, [recipient_email])



# -------------------------------------------------------------
# Creates gift search event when user has a round birthday and sends email
# -------------------------------------------------------------
def create_round_birthday_gift_search():
    now = timezone.localtime(timezone.now())
    print("Gift search job runs at" , now)
    today = now.date()
                                            
    # Get configured offset (days for planning)
    config = JOB_CONFIG['create_round_birthday_gift_search']
    future_search_offset = config.get('future_search_offset', 30)  # start gift search defined days before birthday
    future_search_interval = config.get('interval', 24)  # use the interval to define end of search offset
    future_date_start = today + timedelta(days=future_search_offset)
    future_date_end = future_date_start + timedelta(hours=future_search_interval)
    future_deadline = config.get('deadline', 7)
    
    # Iterate over active user profiles with birthday
    for profile in UserProfile.objects.filter(is_inactive=False, birthday__isnull=False):
        birthday_this_year = profile.birthday.replace(year=today.year)

        # Check if future date matches the user's birthday
        if birthday_this_year >= future_date_start and birthday_this_year <= future_date_end:
            # Calculate age
            age = future_date_start.year - profile.birthday.year
            
            # Check if age is round (multiple of 10)
            if age % 10 == 0:
                # Ensure no auto-generated gift search for this user created yet
                existing_search = GiftSearch.objects.filter(
                    donee=profile,
                    title = f"Birthday Gift for {profile.user.username}",
                    is_auto_generated=True,
                    created_at__year=today.year
                )
                if existing_search.exists():
                    continue  # Skip if one already exists

                # Create new GiftSearch
                event_title = f"Birthday Gift for {profile.user.username}"
                event_purpose = f"We want to find a gift for {profile.user.username}'s {age}th birthday."
                deadline = birthday_this_year - timedelta(days=future_deadline)  # Proposals due in 7 days

                gs = GiftSearch.objects.create(
                    title=event_title,
                    purpose=event_purpose,
                    donee=profile,
                    deadline=deadline,
                    created_by=profile,
                    final_results_sent=False,
                    invitation_sent=True,
                    reminder_sent=False,
                    is_auto_generated=True,
                )

                # Construct URL
                if settings.DEBUG:
                    site_url = "http://127.0.0.1:8000"
                else:
                    site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

                gift_url = site_url + reverse("gift_search_detail", args=[gs.id])

                # Get points for proposal
                config_proposer = GiftConfiguration.objects.filter(role='proposer').first()
                points_proposer = config_proposer.points if config_proposer else 0

                # Get points for voting
                config_voter = GiftConfiguration.objects.filter(role='voter').first()
                points_voter = config_voter.points if config_voter else 0

                # Get points for winning
                config_winner = GiftConfiguration.objects.filter(role='winner').first()
                points_winner = config_winner.points if config_winner else 0

                # Build points details message
                points_message = (
                    "Points available for participating:\n"
                    f"- Propose a gift: {points_proposer} points\n"
                    f"- Vote on proposals: {points_voter} points\n"
                    f"- Winning the gift search: {points_winner} points\n\n"
                )

                # Compose email message
                subject = f"Gift Search Invitation for {profile.user.username}'s {age}th Birthday!"
                base_message = (
                    f"Dear {{username}},\n\n"
                    f"A new gift search has been created in honor of {profile.user.username}'s round birthday ({age} years)!\n\n"
                    f"Purpose: {event_purpose}\n"
                    f"Deadline for proposals: {deadline}\n\n"
                    f"{points_message}"
                    "We invite you to propose a suitable gift for the donee and to vote on proposals.\n\n"
                    f"View the gift search details here: {gift_url}\n\n"
                    "Best regards,\n"
                    "Your 21 Celebrations System"
                )

                # Get all active users except donee
                recipients = UserProfile.objects.filter(is_inactive=False).exclude(pk=profile.pk)
                for recipient in recipients:
                    # Replace placeholder with recipient's username
                    message = base_message.replace("{username}", recipient.user.username)
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [recipient.user.email])



# -------------------------------------------------------------
# Sends mail with payment information to all user who spent money or pay for expenditures for event  (triggered from billing)
# -------------------------------------------------------------
def send_billing_email(user, event, task_payers, honoree_share, transactions):
    # Gather all user profile IDs from passed data
    user_ids = set()
    for _ , uid in task_payers.items():
        user_ids.add(str(uid))
    for uid in honoree_share.keys():
        user_ids.add(str(uid))
    for trans in transactions:
        user_ids.add(str(trans.get('from')))
        user_ids.add(str(trans.get('to')))

    # Get user profiles
    profiles = UserProfile.objects.filter(pk__in=user_ids)
    # Map user profile to username and email
    user_map = {}
    for profile in profiles:
        user_map[str(profile.pk)] = {
            'username': profile.user.username,
            'email': profile.user.email
        }

    # Build task payers table
    task_payers_table = "Task Payers:\n--------------------------\n"
    for taskid, uid in task_payers.items():
        username = user_map.get(str(uid), {}).get('username', "Unknown")
        task = Task.objects.get(event=event, id=taskid)
        task_title = task.title
        amount = task.actual_expenses or 0
        task_payers_table += f"{username}: €{amount} for {task_title}\n"

    # Build honoree share table
    honoree_table = "Honoree Shares:\n--------------------------\n"
    for uid, amount in honoree_share.items():
        username = user_map.get(str(uid), {}).get('username', "Unknown")
        honoree_table += f"{username}: €{amount}\n"

    # Build transactions table
    transactions_table = "Transactions:\n--------------------------\n"
    for trans in transactions:
        debtor_id = str(trans.get('from'))
        receiver_id = str(trans.get('to'))
        amount = trans.get('amount')
        debtor_username = user_map.get(debtor_id, {}).get('username', "Unknown")
        receiver_username = user_map.get(receiver_id, {}).get('username', "Unknown")
        transactions_table += f"From {debtor_username} to {receiver_username}: €{amount}\n"

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    billing_url = site_url + reverse("index")

    # Retrieve penalty configuration from JOB_CONFIG
    payment_frame = JOB_CONFIG.get('check_payment_reminder', {}).get('overdue_threshold', 7)
    payment_penalty = JOB_CONFIG.get('general', {}).get('payment_penalty', -25)

    # Construct mail
    message = (
        "Dear {username},\n\n"
        f"The event '{event.title}' has been billed by {user}. Please find below the billing summary:\n\n"
        f"{task_payers_table}\n\n"
        f"{honoree_table}\n\n"
        f"{transactions_table}\n\n"
        f"If you have an amount to pay (see transactions), please pay it within 7 days. The recipient can confirm the payment here: {billing_url}. "
        f"Please note: if payment is not made within {payment_frame} day(s), a penalty of {payment_penalty} points will be applied to your account.\n\n"
        "Points will be credited at the same time when the recipient confirms the payment.\n\n"
        "Best regards,\n"
        "Your 21 Celebrations System\n\n"
    )
    subject = "Billing Summary"

    # Send email to each user in collected user IDs
    for uid in user_ids:
        if uid in user_map:
            username = user_map[uid]['username']
            email = user_map[uid]['email']
            personalized_message = message.replace("{username}", username)
            send_mail(subject, personalized_message, settings.EMAIL_HOST_USER, [email])
    


# -------------------------------------------------------------
# Sends mail with payment information to all user who contributed to gift contribution
# -------------------------------------------------------------
def send_gift_contribution_billing_email():
    # Get closed gift contributions
    closed_gift_contributions = GiftContribution.objects.filter(status="closed")
    if not closed_gift_contributions.exists():
        return

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")
    
    # Retrieve penalty configuration from JOB_CONFIG
    payment_frame = JOB_CONFIG.get('check_payment_reminder', {}).get('overdue_threshold', 7)
    payment_penalty = JOB_CONFIG.get('general', {}).get('payment_penalty', -25)

    for gc in closed_gift_contributions:
        # Get all transactions related to gift contribution
        transactions = Transaction.objects.filter(gift_search=gc.gift_search, type="gift")
        if not transactions.exists():
            continue  # No transactions to bill
        
        # Group transactions by recipient
        # 1. Manager (to_user) gets all transactions in which he appears
        # 2. Other users, only get transactions where they are contributor (from_user)
        billing_dict = defaultdict(list)
        for trans in transactions:
            # Always add to manager list (to_user)
            manager_id = str(trans.to_user.pk)
            billing_dict[manager_id].append(trans)
            # Add transaction for non-manager
            contributor_id = str(trans.from_user.pk)
            if contributor_id != manager_id:
                billing_dict[contributor_id].append(trans)
        
        # Build billing table for each user and send email
        for user_id, trans_list in billing_dict.items():
            try:
                recipient = UserProfile.objects.get(pk=user_id)
            except UserProfile.DoesNotExist:
                continue

            # Build transactions table
            transactions_table = "Transactions:\n--------------------------\n"
            for t in trans_list:
                from_username = t.from_user.user.username
                to_username = t.to_user.user.username
                transactions_table += f"From {from_username} to {to_username}: €{t.amount}\n"

            # Construct link to dashboard
            billing_url = site_url + reverse("index")
            
            # Compose email message
            message = (
                f"Dear {recipient.user.username},\n\n"
                f"The gift contribution '{gc.title}' has been billed by {gc.manager.user.username}.\n"
                "Please find below the billing summary:\n\n"
                f"{transactions_table}\n\n"
                "If you have an amount to pay (as shown above), please pay it within 7 days. "
                f"The recipient can confirm the payment here: {billing_url}.\n"
                f"Please note: if payment is not made within {payment_frame} day(s), a penalty of {payment_penalty} points will be applied to your account.\n\n"
                "Points will be credited once the recipient confirms the payment.\n\n"
                "Best regards,\n"
                "Your 21 Celebrations System\n\n"
            )
            subject = f"Billing Summary for Gift Contribution '{gc.title}'"
            send_mail(subject, message, settings.EMAIL_HOST_USER, [recipient.user.email])



# -------------------------------------------------------------
# Sends reminder mail for payments/transactions that are overdue
# -------------------------------------------------------------
def check_payment_reminder():
    now = timezone.localtime(timezone.now())
    print("Payment reminder job runs at" , now)

    # Get configured threshold
    config = JOB_CONFIG['check_payment_reminder']
    threshold_offset = config.get('overdue_threshold', 7)  # days after creation of transaction
    overdue_threshold = now - timedelta(minutes=threshold_offset)
    
    # Find transactions created at or before threshold that are not confirmed
    overdue_transactions = Transaction.objects.filter(created_at__lte=overdue_threshold).exclude(status="confirmed")

    # Construct URL
    if settings.DEBUG:
        site_url = "http://127.0.0.1:8000"
    else:
        site_url = getattr(settings, "SITE_URL", "http://21celebrations.com")

    billing_url = site_url + reverse("index")

    # Retrieve penalty configuration from JOB_CONFIG
    payment_frame = JOB_CONFIG.get('check_payment_reminder', {}).get('overdue_threshold', 7)
    payment_penalty = JOB_CONFIG.get('general', {}).get('payment_penalty', -25)

    for transaction in overdue_transactions:
        # Determine the recipient:
        # - If status is "paid", send to recipient (to_user)
        # - Otherwise, send to the payer (from_user)
        if transaction.status == "paid":
            recipient = transaction.to_user
            individual_message = f"{transaction.from_user} has already paid. Please confirm the payment here: {billing_url}. Points will be credited at the same time."
        else:
            recipient = transaction.from_user
            individual_message = f"You have an amount to pay to {transaction.to_user} (see transaction), please pay it immediately. You can change the payment status here: {billing_url}."

        # Build transactions table
        transactions_table = "Transactions:\n--------------------------\n" 
        amount = transaction.amount
        transactions_table += f"From {transaction.from_user} to {transaction.to_user}: €{amount}\n"

        subject = f"Payment Reminder for Transaction {transaction.id}"
        message = (
            f"Dear {recipient},\n\n"
            "This is a reminder that a payment transaction created on "
            f"{transaction.created_at.strftime('%Y-%m-%d')} is now overdue.\n\n"
            "Please check the payment status and take the necessary action.\n\n"
            f"{transactions_table}\n\n"
            f"{individual_message}\n\n"
            f"Please note: if payment is not made within {payment_frame} day(s), a penalty of {payment_penalty} points will be applied to your account.\n\n"
            "Best regards,\n"
            "Your 21 Celebrations System"
        )
        
        send_mail(subject, message, settings.EMAIL_HOST_USER, [recipient.user.email])



# -------------------------------------------------------------
# Checks events and sets status automatically to 'active', 'completed', 'paid'
# -------------------------------------------------------------
def update_event_status():
    # 'planned' → 'active': when date, time, and location are set
    # 'active' → 'completed': when  event date is in past
    # 'billed' → 'paid': when all transactions for event are confirmed

    now = timezone.localtime(timezone.now())
    print("Update event status job runs at" , now)
    today = now.date()
    
    # Process only events that are not canceled
    events = Event.objects.exclude(status='canceled')
    
    for event in events:
        if event.status == 'planned':
            # Check if date, time, and location are set
            if event.date and event.time and event.location:
                event.status = 'active'
                event.save()
        
        elif event.status == 'active':
            # If event date is before today, mark it as completed
            if event.date < today:
                event.status = 'completed'
                event.save()
        
        elif event.status == 'billed':
            # Check if all associated transactions are confirmed
            transactions = Transaction.objects.filter(event=event)
            if transactions.exists():
                if all(t.status == 'confirmed' for t in transactions):
                    event.status = 'paid'
                    event.save()



# -------------------------------------------------------------
# Checks gift contributions and sets status automatically to 'closed' after deadline
# -------------------------------------------------------------
def update_contribution_status():
    # 'XXX' → 'closed': when deadline has passed

    now = timezone.localtime(timezone.now())
    print("Update contribution status job runs at" , now)
    today = now.date()
    
    # Process only contributions that have reached deadline
    contributions = GiftContribution.objects.filter(deadline__lte=today)
    print(contributions)
    for contribution in contributions:
        if contribution.status == 'open':
            contribution.status = "closed"
            contribution.save()
            # Call billing email
            send_gift_contribution_billing_email()

