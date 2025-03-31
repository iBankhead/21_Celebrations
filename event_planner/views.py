import json
from datetime import datetime, date
from collections import defaultdict
from decimal import Decimal
from django.utils import timezone
from django.utils.functional import SimpleLazyObject
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView
from django.contrib import messages
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.forms import NumberInput
from django.db.models import Q
from django import forms
from django.urls import reverse
from django.http import HttpResponseNotAllowed, HttpResponseForbidden, HttpResponseBadRequest, HttpResponse, JsonResponse
from event_planner.scheduler import schedule_jobs
from event_planner.job_config import JOB_CONFIG, save_job_config
from event_planner.jobs import send_billing_email
from vote.models import Vote
from .models import *
from .forms import UserUpdateForm, UserProfileUpdateForm, EventForm, AddRoleForm, TaskForm, TaskEditForm, TaskTemplateForm,\
      RoleConfigurationForm, DeleteEventForm, GiftContributionForm, ContributionForm, GiftSearchForm, GiftProposalForm



# -------------------------------------------------------------
# Use Django's user model
# -------------------------------------------------------------
User = get_user_model()



# -------------------------------------------------------------
# Model which associates tasks with an event and users. It can optionally be based on a task template (through TaskTemplate model)
# -------------------------------------------------------------
def index(request):
    if request.user.is_authenticated:
        # Task section
        # Filter open tasks
        open_statuses = ['pending', 'in_progress', 'overdue', 'reminder']
        open_tasks = Task.objects.filter(assigned_to=request.user.userprofile, status__in=open_statuses)

        # Event section
        # Filter upcoming events
        upcoming_events = Event.objects.filter(date__gt=timezone.now())#
        # Get points awarded for the attendee role (assumed role name "attendee")
        attendee_role = RoleConfiguration.objects.filter(role='attendee').first()
        attendee_points = attendee_role.points if attendee_role else 0

        user_profile = request.user.userprofile
        # Annotate each event with an is_attending attribute
        for event in upcoming_events:
            event.is_attending = event.eventparticipant_set.filter(user_profile=user_profile, role='attendee').exists()
        
        # Score section
        # Fetch RoleScoreHistory, TaskScoreHistory, GiftScoreHistory, PaymentScoreHistory entries for the user
        role_scores = list(RoleScoreHistory.objects.filter(user_profile=user_profile))
        task_scores = list(TaskScoreHistory.objects.filter(user_profile=user_profile))
        gift_scores = list(GiftScoreHistory.objects.filter(user_profile=user_profile))
        payment_scores = list(PaymentScoreHistory.objects.filter(user_profile=user_profile))
        
        # Merge and sort by timestamp (most recent first)
        score_history = sorted(role_scores + task_scores + gift_scores + payment_scores, key=lambda entry: entry.timestamp, reverse=True)
        current_points = request.user.userprofile.total_score

        # Payment section
        #Fetch all transactions with user involved
        transactions = Transaction.objects.filter(Q(from_user=user_profile) | Q(to_user=user_profile)).order_by('-created_at')
        total_sum = sum(-t.amount if t.from_user == user_profile else t.amount for t in transactions)  

        context = {
            'open_tasks': open_tasks,
            'upcoming_events': upcoming_events,
            'attendee_points': attendee_points,
            'current_points': current_points,
            'score_history': score_history,
            "transactions": transactions,
            "total_sum": total_sum,
        }
        return render(request, 'event_planner/index.html', context)
    else:
        return render(request, 'event_planner/index.html', context = {})



# -------------------------------------------------------------
# Function-based view which displays a ranked list of users' scores and historic
# -------------------------------------------------------------
@login_required
def leaderboard(request):
    # Get active profiles (exclude inactive users)
    active_profiles = list(UserProfile.objects.filter(is_inactive=False))

    # Helper function to determine arrow direction based on current vs. past values
    def get_arrow(current, past):
        if current > past:
            return "up"
        elif current < past:
            return "down"
        else:
            return "right"

    # Annotate each profile with arrow fields
    for profile in active_profiles:
        profile.total_arrow = get_arrow(profile.total_score, profile.total_score_past)
        profile.role_arrow = get_arrow(profile.role_score, profile.role_score_past)
        profile.task_arrow = get_arrow(profile.task_score, profile.task_score_past)
        profile.gift_arrow = get_arrow(profile.gift_score, profile.gift_score_past)
        profile.payment_arrow = get_arrow(profile.payment_score, profile.payment_score_past)

    # Helper function builds tied ranking for sorted list of profiles
    # Returns a dictionary mapping profile.id -> rank
    def build_tied_ranking(sorted_profiles, score_field):
        ranking = {}
        current_rank = 0
        prev_score = None
        for i, profile in enumerate(sorted_profiles):
            score = getattr(profile, score_field)
            if prev_score is None or score < prev_score:
                current_rank = i + 1
                prev_score = score
            ranking[profile.id] = current_rank
        return ranking

    # Build tied rankings for past scores for each category
    sorted_past_total = sorted(active_profiles, key=lambda p: p.total_score_past, reverse=True)
    past_total_ranks = build_tied_ranking(sorted_past_total, 'total_score_past')

    sorted_past_roles = sorted(active_profiles, key=lambda p: p.role_score_past, reverse=True)
    past_roles_ranks = build_tied_ranking(sorted_past_roles, 'role_score_past')

    sorted_past_tasks = sorted(active_profiles, key=lambda p: p.task_score_past, reverse=True)
    past_tasks_ranks = build_tied_ranking(sorted_past_tasks, 'task_score_past')

    sorted_past_gifts = sorted(active_profiles, key=lambda p: p.gift_score_past, reverse=True)
    past_gifts_ranks = build_tied_ranking(sorted_past_gifts, 'gift_score_past')

    sorted_past_payments = sorted(active_profiles, key=lambda p: p.payment_score_past, reverse=True)
    past_payments_ranks = build_tied_ranking(sorted_past_payments, 'payment_score_past')

    # Helper function to build a leaderboard for a given score field
    # score_field: current score field name (e.g., 'role_score')
    # past_field: corresponding past score field name (e.g., 'role_score_past')
    # arrow_field: name of the arrow attribute to use (e.g., 'role_arrow')
    # past_ranks: tied ranking mapping from profile.id to past rank
    def build_leaderboard(score_field, past_field, arrow_field, past_ranks):
        # Sort profiles by the current score (descending)
        sorted_current = sorted(active_profiles, key=lambda p: getattr(p, score_field), reverse=True)
        leaderboard = []
        current_rank = 0
        prev_score = None

        # Build dictionary with leaderboard data
        for i, profile in enumerate(sorted_current):
            score = getattr(profile, score_field)
            if prev_score is None or score < prev_score:
                current_rank = i + 1
                prev_score = score
            previous_rank = past_ranks.get(profile.id, current_rank)
            rank_change = previous_rank - current_rank  # positive means improvement
            leaderboard.append({
                'user': profile,
                'current_rank': current_rank,
                'previous_rank': previous_rank,
                'rank_change': rank_change,
                'arrow': getattr(profile, arrow_field)
            })
        return leaderboard

    # Create leaderbord data per leaderboard type
    leaderboard_total = build_leaderboard('total_score', 'total_score_past', 'total_arrow', past_total_ranks)
    leaderboard_roles = build_leaderboard('role_score', 'role_score_past', 'role_arrow', past_roles_ranks)
    leaderboard_tasks = build_leaderboard('task_score', 'task_score_past', 'task_arrow', past_tasks_ranks)
    leaderboard_gifts = build_leaderboard('gift_score', 'gift_score_past', 'gift_arrow', past_gifts_ranks)
    leaderboard_payments = build_leaderboard('payment_score', 'payment_score_past', 'payment_arrow', past_payments_ranks)

    # Prepare historic date for current year
    current_year = date.today().year
    past_scores = PastUserScores.objects.filter(score_date__year=current_year)

    # Helper function to create dictionary for chart
    def build_chart_data(score_field):
        # Group past scores by user
        data_by_user = defaultdict(list)
        all_dates = set()
        for ps in past_scores:
            data_by_user[ps.user.username].append((ps.score_date, getattr(ps, score_field)))
            all_dates.add(ps.score_date)
        # Sort dates and format as strings "YYYY-MM-DD"
        labels = sorted(all_dates)
        labels = [d.strftime("%Y-%m-%d") for d in labels]
        
        datasets = []
        # Generate unique color for each dataset using HSL
        total_users = len(data_by_user)
        for i, (username, values) in enumerate(sorted(data_by_user.items())):
            # Calculate hue evenly spaced over 360 degrees
            hue = int((i * 360 / total_users) % 360)
            color = f"hsl({hue}, 70%, 50%)"
            # Build dictionary mapping date to score
            score_dict = {d: score for d, score in values}
            data_array = []
            for label in labels:
                d = date.fromisoformat(label)
                data_array.append(score_dict.get(d, None))

            datasets.append({
                "label": username,
                "data": data_array,
                "fill": False,
                "borderColor": color,
                "backgroundColor": color,
                "tension": 0.1,
            })
        return {"labels": labels, "datasets": datasets}

    # Create chart with historic data per score type
    historic_total_json = json.dumps(build_chart_data("total_score"))
    historic_role_json = json.dumps(build_chart_data("role_score"))
    historic_task_json = json.dumps(build_chart_data("task_score"))
    historic_gift_json = json.dumps(build_chart_data("gift_score"))
    historic_payment_json = json.dumps(build_chart_data("payment_score"))

    context = {
        'leaderboard_total': leaderboard_total,
        'leaderboard_roles': leaderboard_roles,
        'leaderboard_tasks': leaderboard_tasks,
        'leaderboard_gifts': leaderboard_gifts,
        'leaderboard_payments': leaderboard_payments,
        'historic_total_json': historic_total_json,
        'historic_role_json': historic_role_json,
        'historic_task_json': historic_task_json,
        'historic_gift_json': historic_gift_json,
        'historic_payment_json': historic_payment_json,
    }

    return render(request, 'event_planner/leaderboard.html', context)



# -------------------------------------------------------------
# Function-based view which displays a calendar with all dates (birthday, event, task, gift search)
# -------------------------------------------------------------
@login_required
def calendar_view(request):
    calendar_events = []
    now = timezone.now()
    current_year = now.year
    today = now.date()

    # Birthdays: Show each user's birthday (year-adjusted)
    birthdays = UserProfile.objects.exclude(birthday__isnull=True)
    for profile in birthdays:
        bday = profile.birthday
        try:
            birthday_this_year = bday.replace(year=current_year)
        except ValueError:
            # Handle Feb 29 on non-leap years
            birthday_this_year = bday.replace(year=current_year, day=bday.day-1)
        calendar_events.append({
            'title': f"{profile.user.username}'s Birthday",
            'start': birthday_this_year.strftime("%Y-%m-%d"),
            'color': 'DarkCyan',       
            'textColor': 'White', 
            'extendedProps': {
                'icon': 'bi bi-person-bounding-box',  
                'type': 'birthday'
            }
        })

    # Events: Only events with date, time, and location set
    events = Event.objects.filter(date__isnull=False, time__isnull=False, location__isnull=False)
    for event in events:
        calendar_events.append({
            'title': f"{event.title}",
            'start': event.date.isoformat(),
            'color': 'ForestGreen', 
            'textColor': 'White',
            'extendedProps': {
                'icon': 'bi bi-balloon',
                'type': 'event'
            }
        })

    # Tasks: Only tasks for the logged-in user
    tasks = Task.objects.filter(assigned_to=request.user.userprofile)
    for task in tasks:
        due_date_str = task.due_date.strftime("%Y-%m-%d") if hasattr(task.due_date, 'strftime') else str(task.due_date)
        overdue = False
        task_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
        if task_date < today and task.status != 'completed':
            overdue = True
        icon = 'bi bi-briefcase'
        if overdue:
            icon = 'bi bi-exclamation-triangle'
        calendar_events.append({
            'title': f"Task: {task.title}" + (" (Overdue)" if overdue else ""),
            'start': due_date_str,
            'color': 'RoyalBlue', 
            'textColor': 'White',
            'extendedProps': {
                'icon': icon,
                'type': 'task',
                'status': task.status
            }
        })
        if overdue:
            calendar_events.append({
                'start': due_date_str,
                'color': 'Red',
                'textColor': 'White',
                'title': 'overdue'
            })

    # Gift Searches: Exclude searches where the logged-in user is donee
    gift_searches = GiftSearch.objects.filter(deadline__isnull=False).exclude(donee=request.user.userprofile)
    for gs in gift_searches:
        calendar_events.append({
            'title': f"Gift Search: {gs.title}",
            'start': gs.deadline.isoformat(),
            'color': 'DarkMagenta',
            'textColor': 'White',
            'extendedProps': {
                'icon': 'bi bi-gift',
                'type': 'gift'
            }
        })

    # Gift Contributions: Exclude contributions where the logged-in user is donee
    gift_contributions = GiftContribution.objects.filter(deadline__isnull=False).exclude(donee=request.user.userprofile)
    for gc in gift_contributions:
        calendar_events.append({
            'title': f"Gift Contribution: {gc.title}",
            'start': gc.deadline.isoformat(),
            'color': 'BlueViolet',
            'textColor': 'White',
            'extendedProps': {
                'icon': 'bi bi-cash-coin',
                'type': 'gift'
            }
        })

    context = {
        'calendar_events_json': json.dumps(calendar_events)
    }
    return render(request, 'event_planner/calendar.html', context)



# -------------------------------------------------------------
# Class-based view which lists all upcomimg events in asscending order
# -------------------------------------------------------------
class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'event_planner/event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        today = timezone.now().date()
        return Event.objects.filter(
            date__gte=today, 
            status__in=['planned', 'active'],
        ).order_by('date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = self.request.user.userprofile
        for event in context["events"]:
            # Check if user is manager, organizer, or honouree of event
            event.can_edit = event.eventparticipant_set.filter(
                user_profile=user_profile, 
                role__in=["manager", "organizer", "honouree"]
            ).exists()
        return context



# -------------------------------------------------------------
# Class-based view which lists all events in planning
# -------------------------------------------------------------
class EventPlannedView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'event_planner/event_planned.html'
    context_object_name = 'events'

    def get_queryset(self):
        user_profile = self.request.user.userprofile
        return Event.objects.filter(
            date__isnull=True,
            eventparticipant__user_profile=user_profile,
            eventparticipant__role__in=["manager", "organizer", "honouree"],
            status__in=['planned', 'active'],
        ).order_by('title').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = self.request.user.userprofile
        for event in context['events']:
            event.can_delete = event.eventparticipant_set.filter(user_profile=user_profile, role="manager").exists()
        return context



# -------------------------------------------------------------
# Class-based view which lists all completed, billed, paid events
# -------------------------------------------------------------
class EventFinalView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'event_planner/event_final.html'
    context_object_name = 'events'

    def get_queryset(self):
        user_profile = self.request.user.userprofile
        return Event.objects.filter(
            eventparticipant__user_profile=user_profile,
            eventparticipant__role__in=["manager"],
            status__in=['completed', 'billed', 'paid'],
        ).order_by('-date').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = self.request.user.userprofile
        for event in context['events']:
            tasks = Task.objects.filter(event=event, is_cost_related=True)
            # Calculated total budget and expenses from tasks
            event.total_actual = sum(task.actual_expenses or 0 for task in tasks)
            event.total_budget = sum(task.budget or 0 for task in tasks)
            event.deviation = event.total_budget - event.total_actual
            if event.status in ['completed']:
                event.can_bill = event.eventparticipant_set.filter(user_profile=user_profile, role="manager").exists()
            else:
                event.see_trans = event.eventparticipant_set.filter(user_profile=user_profile, role="manager").exists()
        return context



# -------------------------------------------------------------
# Function-based view which divides the costs between honorees
# -------------------------------------------------------------
@login_required
def clearing_view(request, event_id):
    # Get event and cost related tasks
    event = get_object_or_404(Event, id=event_id)
    tasks = Task.objects.filter(event=event, is_cost_related=True)
    
    # Calculated total budget and expenses from tasks
    total_actual = sum(task.actual_expenses or 0 for task in tasks)
    total_budget = sum(task.budget or 0 for task in tasks)
    
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "bill_transactions":
            # Retrieve data from hidden fields
            payer_data_json = request.POST.get("payer_data")
            honoree_data_json = request.POST.get("honoree_data")
            payer_data_json = request.POST.get("payer_data")
            try:
                decoded_str = payer_data_json.encode('utf-8').decode('unicode_escape')
                payer_dict = json.loads(decoded_str)
                honoree_ids = json.loads(honoree_data_json)
            except Exception as e:
                messages.error(request, "Error parsing payer data: " + str(e))
                return redirect("clearing_view", event_id=event_id)
            
            payer_dict = {int(k): v for k, v in payer_dict.items()}

            # Retrieve user profiles for selected honorees
            selected_profiles_honorees = UserProfile.objects.filter(id__in=honoree_ids)

            # Calculate how much each selected honoree already paid (as payer of task)
            pos = []  # Receivers of transactions
            payer_ids = []
            paid_by = {}
            for task in tasks:
                payer = payer_dict.get(task.id)
                # Classify payers as honorees or receivers
                if payer in honoree_ids:
                    paid_by[payer] = paid_by.get(payer, 0) + (task.actual_expenses or 0)
                else:
                    net = (task.actual_expenses or 0)
                    pos.append([payer, net])
                    payer_ids.append(payer)
            
            # Retrieve user profiles for selected payers
            selected_profiles_payers = UserProfile.objects.filter(id__in=payer_ids)

            # Set paymenmts to 0 for honorees who are not payers of task
            for honoree_id in honoree_ids:
                if honoree_id not in paid_by:
                    paid_by[honoree_id] = 0
            
            # Compute share per selected honoree
            share = total_actual / len(honoree_ids) if honoree_ids else 0
            
            # Compute net balance for each selected honoree
            total_net = 0
            division_results = {}
            for honoree_id in honoree_ids:
                division_results[honoree_id] = paid_by.get(honoree_id, 0) - share
                total_net += division_results[honoree_id]

            # Build lists for transaction generation
            neg = []  # Payers of transactions
            for honoree_id, net_value in division_results.items():
                if net_value > 0:
                    pos.append([honoree_id, net_value])
                elif net_value < 0:
                    neg.append([honoree_id, -net_value])
            
            pos.sort(key=lambda x: x[1], reverse=True)
            neg.sort(key=lambda x: x[1])

            # Each transaction: {'from': debtor id, 'to': receiver id, 'amount': value}
            transactions = []  
            total_trans = 0
            i, j = 0, 0
            while i < len(neg) and j < len(pos):
                debtor, debt_amt = neg[i]
                creditor, credit_amt = pos[j]
                trans_amt = min(debt_amt, credit_amt)
                total_trans += trans_amt
                transactions.append({
                    'from': debtor,
                    'to': creditor,
                    'amount': trans_amt
                })
                neg[i][1] -= trans_amt
                pos[j][1] -= trans_amt
                if neg[i][1] == 0:
                    i += 1
                if pos[j][1] == 0:
                    j += 1
            
            # Sum transactions by from, to if possible (reduce lines)
            grouped = defaultdict(Decimal)
            for t in transactions:
                key = (t['from'], t['to'])
                grouped[key] += t['amount']

            summed_transactions = [{'from': k[0], 'to': k[1], 'amount': amt} for k, amt in grouped.items()]
            
            # Write transactions to database
            for trans in summed_transactions:
                debtor = UserProfile.objects.get(id=trans['from'])
                creditor = UserProfile.objects.get(id=trans['to'])
                Transaction.objects.create(
                    from_user=debtor,
                    to_user=creditor,
                    amount=trans['amount'],
                    type='event',
                    event=event,
                    status='billed',
                    created_by=request.user.userprofile,
                )
            
            # Write 'dummy' transactions for payments of honoree (necessary for points)
            for honoree_id in honoree_ids:
                if paid_by.get(honoree_id, 0) > 0:
                    honoree = UserProfile.objects.get(id=honoree_id)
                    Transaction.objects.create(
                        from_user=honoree,
                        to_user=honoree,
                        amount=paid_by.get(honoree_id, 0),
                        type='event',
                        event=event,
                        status='confirmed',
                        created_by=request.user.userprofile,
                    )                   

            # Change event status to 'billed'
            event.status = 'billed'
            event.save()
            
            # If "send_mail" checkbox is checked, call billing email job
            if request.POST.get("send_mail"):
                send_billing_email(request.user.userprofile, event, payer_dict, division_results, summed_transactions)
            
            messages.success(request, "Transactions billed successfully and event marked as billed.")
            return redirect("event_final")
        
        else:
            # Get defined payers of tasks (only one assigned user can be payer)
            payer_dict = {} 
            for task in tasks:
                payer_value = request.POST.get(f"task_{task.id}_payer")
                if not payer_value:
                    messages.error(request, f"Please select a payer for task '{task.title}'.")
                    return redirect("clearing_view", event_id=event.id)
                try:
                    payer_dict[task.id] = int(payer_value)
                except (ValueError, TypeError):
                    messages.error(request, f"Invalid payer selection for task '{task.title}'.")
                    return redirect("clearing_view", event_id=event.id)
            
            # Get selected honorees from the form
            selected_honorees = request.POST.getlist("honorees")
            try:
                honoree_ids = [int(x) for x in selected_honorees]
            except ValueError:
                honoree_ids = []
            if not honoree_ids:
                messages.error(request, "Please select at least one honoree for cost sharing.")
                return redirect("clearing_view", event_id=event.id)
            
            # Retrieve user profiles for selected honorees
            selected_profiles_honorees = UserProfile.objects.filter(id__in=honoree_ids)

            # Calculate how much each selected honoree already paid (as payer of task)
            pos = []  # Receivers of transactions
            payer_ids = []
            paid_by = {}
            for task in tasks:
                payer = payer_dict.get(task.id)
                # Classify payers as honorees or receivers
                if payer in honoree_ids:
                    paid_by[payer] = paid_by.get(payer, 0) + (task.actual_expenses or 0)
                else:
                    net = (task.actual_expenses or 0)
                    pos.append([payer, net])
                    payer_ids.append(payer)
            
            # Retrieve user profiles for selected payers
            selected_profiles_payers = UserProfile.objects.filter(id__in=payer_ids)

            # Set paymenmts to 0 for honorees who are not payers of task
            for honoree_id in honoree_ids:
                if honoree_id not in paid_by:
                    paid_by[honoree_id] = 0
            
            # Compute share per selected honoree
            share = total_actual / len(honoree_ids) if honoree_ids else 0
            
            # Compute net balance for each selected honoree
            total_net = 0
            division_results = {}
            for honoree_id in honoree_ids:
                division_results[honoree_id] = paid_by.get(honoree_id, 0) - share
                total_net += division_results[honoree_id]

            # Build lists for transaction generation:
            neg = []  # Payers of transactions
            for honoree_id, net_value in division_results.items():
                if net_value > 0:
                    pos.append([honoree_id, net_value])
                elif net_value < 0:
                    neg.append([honoree_id, -net_value])
            
            pos.sort(key=lambda x: x[1], reverse=True)
            neg.sort(key=lambda x: x[1])

            # Each transaction: {'from': debtor id, 'to': receiver id, 'amount': value}
            transactions = []  
            total_trans = 0
            i, j = 0, 0
            while i < len(neg) and j < len(pos):
                debtor, debt_amt = neg[i]
                creditor, credit_amt = pos[j]
                trans_amt = min(debt_amt, credit_amt)
                total_trans += trans_amt
                transactions.append({
                    'from': debtor,
                    'to': creditor,
                    'amount': trans_amt
                })
                neg[i][1] -= trans_amt
                pos[j][1] -= trans_amt
                if neg[i][1] == 0:
                    i += 1
                if pos[j][1] == 0:
                    j += 1
            
            # Sum transactions by from, to if possible (reduce lines)
            grouped = defaultdict(Decimal)
            for t in transactions:
                key = (t['from'], t['to'])
                grouped[key] += t['amount']

            summed_transactions = [{'from': k[0], 'to': k[1], 'amount': amt} for k, amt in grouped.items()]

            context = {
                "event": event,
                "tasks": tasks,
                "total_actual": total_actual,
                "total_budget": total_budget,
                "share": share,
                "division_results": division_results,
                "selected_honorees": honoree_ids,
                "selected_profiles": selected_profiles_honorees,
                "selected_payers": selected_profiles_payers,
                "paid_by": paid_by,
                "transactions": summed_transactions,
                "total_net": total_net,
                "total_trans": total_trans,
                "payer_dict_json": json.dumps(payer_dict, cls=DjangoJSONEncoder),
                "honoree_ids_json": json.dumps(honoree_ids),
            }
            return render(request, "event_planner/clearing_results.html", context)
    
    else:
        context = {
            "event": event,
            "tasks": tasks,
            "total_actual": total_actual,
            "total_budget": total_budget,
        }
        return render(request, "event_planner/clearing_form.html", context)



# -------------------------------------------------------------
# Function-based view which lists all transactions of event
# -------------------------------------------------------------
@login_required
def event_transactions(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    transactions = Transaction.objects.filter(event=event).order_by("from_user")
    context = {
        "event": event,
        "transactions": transactions,
        "now": timezone.now(),
    }
    return render(request, "event_planner/event_transactions.html", context)



# -------------------------------------------------------------
# Function-based view which allows to delete planned event
# -------------------------------------------------------------
@login_required
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == "POST":
        form = DeleteEventForm(request.POST)
        if form.is_valid():
            event.delete()
            return redirect('event_planned')
    else:
        form = DeleteEventForm()
    return render(request, 'event_planner/delete_event_confirm.html', {'form': form, 'event': event})
    


# -------------------------------------------------------------
# Function-based view which allows to edit the user's profile
# -------------------------------------------------------------
@login_required
def personal_data(request):
    if request.method == 'POST':
        # Get forms with user data
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileUpdateForm(request.POST, instance=request.user.userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            # Inactive users get no notificaations
            if profile_form.cleaned_data.get('is_inactive'):
                messages.info(request, "Your user has been deactivated. You cannot participate in events.")

            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('personal_data')
        else:
            # Iterate over errors
            for field, error_list in profile_form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")

            messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileUpdateForm(instance=request.user.userprofile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'create_event_url': reverse('create_event'),
    }
    return render(request, 'event_planner/personal_data.html', context)



# -------------------------------------------------------------
# Function-based view which allows to delete an account
# -------------------------------------------------------------
@login_required
def delete_account(request):
    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            # Delete user account and log user out
            request.user.delete()
            logout(request)
            return redirect('account_deleted')  # Redirect to a confirmation page
        else:
            # Retrieve the next URL from form data
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)
            # Fallback if next is not provided
            return redirect('/')
    # On GET, pass active URL to "next" or default to '/'
    next_url = request.META.get('HTTP_REFERER', '/')
    return render(request, 'event_planner/delete_account.html', {'next': next_url})



# -------------------------------------------------------------
# Function-based view which allows to delete an account
# -------------------------------------------------------------
@login_required
def attend_from_mail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Create the participant record (assuming request.user is a User)
    event.eventparticipant_set.get_or_create(user_profile=request.user.userprofile, role='attendee')
    return render(request, "event_planner/attend_event_success.html", {"event": event})



# -------------------------------------------------------------
# Function-based view which allows to creates a new event manually
# -------------------------------------------------------------
@login_required
def create_event(request):
    event_type = request.GET.get('event_type')
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user 
            # Other fields are set automatically via model defaults (is_auto_generated, status, created_at, etc.)
            event.save()
            # Automatically assign creator as a manager
            user_profile = request.user.userprofile
            EventParticipant.objects.create(event=event, user_profile=user_profile, role='manager')
            messages.success(request, "Event created successfully!")
            
            # Redirect to edit_detail_page after creation
            redirect_url = reverse('edit_event_detail', kwargs={'event_id': event.id})
            return HttpResponse(f'<script type="text/javascript">window.top.location.href = "{redirect_url}";</script>')
        else:
            # Iterate over errors
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")

            messages.error(request, "Please correct the errors below.")
    else:
        # Set initial value for event_type if provided in query parameters
        if event_type:
            form = EventForm(initial={'event_type': event_type})
        else:
            form = EventForm()
    return render(request, 'event_planner/create_event.html', {'form': form})



# -------------------------------------------------------------
# Function-based view which allows to view/edit an event manually
# -------------------------------------------------------------
@login_required
def edit_event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    is_manager = event.eventparticipant_set.filter(role='manager', user_profile__user=request.user).exists()
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.updated_by = request.user 
            event.save()
            messages.success(request, "Event updated successfully!")
            # Redirect back to the same page after updating
            return redirect('edit_event_detail', event_id=event.id)
        else:
            # Iterate over each field's errors
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")

            messages.error(request, "Please correct the errors below.")
    else:
        form = EventForm(instance=event)

    # Instantiate forms for different tasks
    task_form = TaskForm(event=event)
    edit_task_form = TaskEditForm(event=event)
    role_form = AddRoleForm()

    context = {
        'event': event,
        'form': form,   # Used for editing event
        'task_form': task_form,     # Used for create tasks
        'edit_task_form': edit_task_form,   # Used for editing tasks
        'role_form': role_form,     # Used for editing roles
        'is_manager': is_manager,
    }
    return render(request, 'event_planner/edit_event_detail.html', context)



# -------------------------------------------------------------
# Function-based view which allows to creates a new role for an event manually
# -------------------------------------------------------------
@login_required
def add_role(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Process only POST requests
    if request.method == 'POST':
        form = AddRoleForm(request.POST)
        if form.is_valid():
            user_profile = form.cleaned_data['user_profile']
            role = form.cleaned_data['role']
            existing = EventParticipant.objects.filter(event=event, user_profile=user_profile, role=role).exists()
            if existing:
                messages.warning(request, "This role is already assigned to the user for this event.")
            else:
                EventParticipant.objects.create(event=event, user_profile=user_profile, role=role)
                messages.success(request, "Role added successfully.")
        else:
            messages.error(request, "There was an error adding the role. Please check the details.")
        return redirect('edit_event_detail', event_id=event.id)
    else:
        return redirect('edit_event_detail', event_id=event.id)



# -------------------------------------------------------------
# Function-based view which allows to delete a role for an event manually
# -------------------------------------------------------------
@login_required
def delete_role(request, event_id):
    if request.method == 'POST':
        participant_id = request.POST.get('participant_id', '').strip()
        if not participant_id:
            messages.error(request, "No participant specified for deletion.")
            return redirect('edit_event_detail', event_id=event_id)
        try:
            participant_id_int = int(participant_id)
        except ValueError:
            messages.error(request, "Invalid participant ID.")
            return redirect('edit_event_detail', event_id=event_id)
        
        participant = get_object_or_404(EventParticipant, id=participant_id_int, event__id=event_id)
        
        # If the participant's role is 'manager', ensure there's more than one manager
        if participant.role == 'manager':
            manager_count = participant.event.eventparticipant_set.filter(role='manager').count()
            if manager_count <= 1:
                messages.error(request, "Cannot delete the only manager for this event.")
                return redirect('edit_event_detail', event_id=event_id)
        
        participant.delete()
        messages.success(request, "Participant deleted successfully.")
        return redirect('edit_event_detail', event_id=event_id)
    else:
        return HttpResponseNotAllowed(['POST'])
    


# -------------------------------------------------------------
# Function-based view which allows to create tasks for an event manually 
# -------------------------------------------------------------
@login_required
def add_task(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Refresh the event instance to ensure its related participants are up-to-date
    event.refresh_from_db()   
    if request.method == 'POST':       
        form = TaskForm(request.POST, request.FILES, event=event)
        if form.is_valid():
            task = form.save(commit=False)
            task.event = event
            task.save()
            form.save_m2m()
            messages.success(request, "Task added successfully.")
            return redirect('edit_event_detail', event_id=event.id)
        else: 
            # Iterate over each field's errors
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}") 

            messages.error(request, "Please correct the errors below.")
    else:
        form = TaskForm(event=event)
    
    context = {'form': form, 'event': event,}
    return render(request, 'event_planner/add_task_modal.html', context)



# -------------------------------------------------------------
# Function-based view which allows to edit a task manually
# -------------------------------------------------------------
@login_required
def edit_task(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        task = get_object_or_404(Task, id=task_id, event=event)

        data = request.POST.copy()

        # Instantiate the form with POST data, FILES, and the event parameter
        form = TaskEditForm(request.POST, request.FILES, instance=task, event=event)

        # Force-reset the queryset for the assigned_to field
        allowed_ids = list(
            event.eventparticipant_set.filter(
                role__in=['manager', 'organizer', 'honouree']
            ).values_list('user_profile__id', flat=True)
        )
        form.fields['assigned_to'].queryset = UserProfile.objects.filter(id__in=allowed_ids)
        
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            messages.success(request, "Task updated successfully.")
            return redirect('edit_event_detail', event_id=event.id)
        else:
            # Iterate over each field's errors
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")

            messages.error(request, "Please correct the errors below.")

            open_edit_task_modal = True
            # Re-render the page with the form
            is_manager = event.eventparticipant_set.filter(role='manager', user_profile__user=request.user).exists()
            context = {
                'event': event,
                'form': EventForm(instance=event),  # event form
                'edit_task_form': form,             # bound TaskEditForm with errors
                'add_role_form': AddRoleForm(),
                'is_manager': is_manager,
                'open_edit_task_modal': open_edit_task_modal,
            }
            return render(request, 'event_planner/edit_event_detail.html', context)
    else:
        return redirect('edit_event_detail', event_id=event.id)



# -------------------------------------------------------------
# Function-based view which displays lists for gift and event task templates
# -------------------------------------------------------------
@login_required
def task_template_list(request):
    event_templates = TaskTemplate.objects.filter(task_type='event')
    gift_templates = TaskTemplate.objects.filter(task_type='gift')
    return render(request, 'event_planner/task_template_list.html', {
        'event_templates': event_templates,
        'gift_templates': gift_templates,
    })



# -------------------------------------------------------------
# Function-based view which allows to creates task templates
# -------------------------------------------------------------
@login_required
def create_task_template(request):
    if request.method == 'POST':
        # POST request, task_type comes from hidden input
        form = TaskTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        # GET requests
        form = TaskTemplateForm()
    return render(request, 'event_planner/create_task_template.html', {'form': form})



# -------------------------------------------------------------
# Function-based view which allows to edit task templates
# -------------------------------------------------------------
@login_required
def edit_task_template(request, template_id):
    template = get_object_or_404(TaskTemplate, pk=template_id)
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = TaskTemplateForm(instance=template)
    return render(request, 'event_planner/edit_task_template.html', {'form': form, 'template': template})



# -------------------------------------------------------------
# Function-based view which allows to delete a task template
# -------------------------------------------------------------
@login_required
def delete_task_template(request, template_id):
    template = get_object_or_404(TaskTemplate, pk=template_id)
    if request.method == 'POST':
        template.delete()
        return JsonResponse({'success': True})
    return render(request, 'event_planner/delete_task_template_confirm.html', {'template': template})



# -------------------------------------------------------------
# Function-based view to return task data as JSON
# -------------------------------------------------------------
@login_required
def get_task_data(request, event_id, task_id):
    task = get_object_or_404(Task, id=task_id, event__id=event_id)
    local_due_date = timezone.localtime(task.due_date)
    data = {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'notes': task.notes,
        #'due_date': task.due_date.strftime('%Y-%m-%dT%H:%M') if task.due_date else '',
        'due_date': local_due_date.strftime('%Y-%m-%dT%H:%M'),
        'status': task.status,
        'is_cost_related': task.is_cost_related,
        'budget': task.budget if task.budget is not None else '',
        'actual_expenses': task.actual_expenses if task.actual_expenses is not None else '',
        'base_points': task.base_points if task.base_points is not None else '',
        'penalty_points': task.penalty_points if task.penalty_points is not None else '',
        'assigned_to': list(task.assigned_to.values_list('id', flat=True)),
        'attachment_url': request.build_absolute_uri(task.attachment.url) if task.attachment else None,
        'template': task.template.id if task.template else '',
    }
    return JsonResponse(data)



# -------------------------------------------------------------
# Function-based view which overtakes template values into task
# -------------------------------------------------------------
@login_required
def get_template_defaults(request, template_id):
    template = get_object_or_404(TaskTemplate, id=template_id)
    data = {
        'title': template.title,
        'description': template.description,
        'base_points': template.base_points,
        'penalty_points': template.penalty_points,
    }
    return JsonResponse(data)



# -------------------------------------------------------------
# Function-based view which allows to delete a task manually
# -------------------------------------------------------------
@login_required
def delete_task(request, event_id):
    if request.method == 'POST':
        task_id = request.POST.get('task_id', '').strip()
        if not task_id:
            messages.error(request, "No task specified for deletion.")
            return redirect('edit_event_detail', event_id=event_id)
        event = get_object_or_404(Event, id=event_id)
        task = get_object_or_404(Task, id=task_id, event=event)
        task.delete()
        messages.success(request, "Task deleted successfully.")
        return redirect('edit_event_detail', event_id=event_id)
    else:
        return HttpResponseNotAllowed(['POST'])
    


# -------------------------------------------------------------
# Function-based view which allows to update task stats in the dashboard
# -------------------------------------------------------------
@login_required
def update_task_status(request, task_id):
    if request.method == "POST":
        new_status = request.POST.get("status")
        allowed_statuses = ['in_progress', 'completed']

        if new_status not in allowed_statuses:
            return HttpResponseBadRequest("Invalid status")

        # Retrieve the task the user is assigned to
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user.userprofile)

        task.status = new_status
        task.save()

        # Redirect to dashboard)
        return redirect('index')
    else:
        return HttpResponseBadRequest("Only POST requests are allowed.")



# -------------------------------------------------------------
# Function-based view which allows to update task details in the dashboard
# -------------------------------------------------------------
@login_required
def update_task_detail(request):
    if request.method == "POST":
        # Retrieve task id from the hidden input
        task_id = request.POST.get("task_id")
        if not task_id:
            return HttpResponseBadRequest("Task ID is missing.")
        
        # Retrieve task
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user.userprofile)

        # Update actual_expenses if provided
        actual_expenses = request.POST.get("actual_expenses")
        if actual_expenses:
            try:
                task.actual_expenses = Decimal(actual_expenses)
            except Exception:
                return HttpResponseBadRequest("Invalid value for actual expenses.")

        # Process uploaded file (if provided)
        if "attachment" in request.FILES:
            task.attachment = request.FILES["attachment"]

        # Save changes
        task.save()

        # Redirect to the index/dashboard page (adjust as needed)
        return redirect("index")
    else:
        return HttpResponseBadRequest("Only POST requests are allowed.")



# -------------------------------------------------------------
# Function-based view which allows to attend an event in the dashboard
# -------------------------------------------------------------
@login_required
def attend_event(request, event_id):
    if request.method == "POST":
        # Retrieve event and userprofile
        event = get_object_or_404(Event, id=event_id)
        user_profile = request.user.userprofile

        # Check if user is already an attendee
        if not event.eventparticipant_set.filter(user_profile=user_profile, role='attendee').exists():
            # Create a new participant record for the attendee role.
            event.eventparticipant_set.create(user_profile=user_profile, role='attendee')
        
        # Redirect back to the dashboard
        return redirect('index')
    else:
        return HttpResponseBadRequest("Invalid request method.")
    


# -------------------------------------------------------------
# Function-based view which allows to decline an event in the dashboard
# -------------------------------------------------------------
@login_required
def decline_event(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(Event, id=event_id)
        user_profile = request.user.userprofile

        # Remove the attendee record if it exists
        event.eventparticipant_set.filter(user_profile=user_profile, role='attendee').delete()
        return redirect('index')
    else:
        return HttpResponseBadRequest("Invalid request method.")


# -------------------------------------------------------------
# Function-based view which allows to handle payments in the dashboard
# -------------------------------------------------------------
@login_required
def update_payment(request, transaction_id):
    user_profile = request.user.userprofile
    transaction = get_object_or_404(Transaction, id=transaction_id)

    if request.method == "POST":
        # If user is sender and status is "billed", mark as "paid"
        if transaction.from_user == user_profile and transaction.status == "billed":
            transaction.status = "paid"
            transaction.save()
            messages.success(request, "Transaction status updated to paid.")
        # If user is receiver and status is "paid", mark as "confirmed"
        elif transaction.to_user == user_profile and transaction.status == "paid":
            transaction.status = "confirmed"
            transaction.save()
            messages.success(request, "Transaction status updated to confirmed.")
        else:
            messages.error(request, "You are not allowed to update this transaction or no update is necessary.")
    return redirect('index')



# -------------------------------------------------------------
# Function-based view which allows to start a new gift search
# -------------------------------------------------------------
@login_required
def create_gift_search(request):
    if request.method == 'POST':
        form = GiftSearchForm(request.POST)
        if form.is_valid():
            gift_search = form.save(commit=False)
            gift_search.created_by = request.user.userprofile
            gift_search.save()

            # Redirect to gift proposal page
            redirect_url = reverse('gift_search_detail', kwargs={'search_id': gift_search.id})
            return HttpResponse(
                f'<script type="text/javascript">window.top.location.href = "{redirect_url}";</script>'
            )
        else:
            # Iterate over each errors to add messages
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = GiftSearchForm()
    return render(request, 'event_planner/create_gift_search.html', {'form': form})



# -------------------------------------------------------------
# Function-based view which displays open gift searches (donee does not see search)
# -------------------------------------------------------------
@login_required
def gift_list(request):
    now = timezone.now().date()
    gift_searches = GiftSearch.objects.filter(deadline__gt=now).exclude(donee=request.user.userprofile)
    return render(request, 'event_planner/gift_list.html', {'gift_searches': gift_searches})



# -------------------------------------------------------------
# Function-based view which displays closed gift searches (donee excluded)
# -------------------------------------------------------------
@login_required
def closed_gift_list(request):
    today = timezone.now().date()
    # Filter searches with deadline >= today and exclude those for which current user is donee
    closed_searches = GiftSearch.objects.filter(deadline__lte=today).exclude(donee=request.user.userprofile).order_by('-deadline')
    
    # Prepare data for each search
    search_data = []
    for search in closed_searches:
        proposals = search.proposals.all()
        best_proposal = None
        best_vote_count = -1
        # FInd best voted proposal
        for proposal in proposals:
            vote_count = proposal.votes.count()
            if vote_count > best_vote_count:
                best_vote_count = vote_count
                best_proposal = proposal
        
        # Get voters for this proposal
        sorted_voters = []
        if best_proposal:
            ct = ContentType.objects.get_for_model(best_proposal)
            votes = Vote.objects.filter(content_type=ct, object_id=best_proposal.id)
            sorted_voters = sorted(votes, key=lambda v: User.objects.get(id=v.user_id).username)
            #sorted_voters = sorted(votes, key=lambda v: User.objects.get(id=v.user_id).username)
                    
        search_data.append({
            'search': search,
            'best_proposal': best_proposal,
            'vote_count': best_vote_count,
            'sorted_voters': sorted_voters,
        })
    context = {'closed_searches': search_data}

    return render(request, 'event_planner/closed_gift_list.html', context)


# -------------------------------------------------------------
# Function-based view which displays proposals for a specific gift search
# -------------------------------------------------------------
@login_required
def gift_search_detail(request, search_id):
    gift_search = get_object_or_404(GiftSearch, id=search_id)
    # Prevent donee from viewing this section
    if gift_search.donee == request.user.userprofile:
        return HttpResponseForbidden("You are not allowed to view this page.")
    
    # Get all proposals and sort by vote count (descending)
    proposals = list(gift_search.proposals.all())
    proposals.sort(key=lambda p: p.votes.count(), reverse=True)
    
    if request.method == 'POST':
        form = GiftProposalForm(request.POST, request.FILES)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.gift_search = gift_search
            proposal.proposed_by = request.user.userprofile
            proposal.save()
            return redirect('gift_search_detail', search_id=search_id)
    else:
        form = GiftProposalForm()
    
    context = {
        'gift_search': gift_search,
        'proposals': proposals,
        'form': form,
    }
    return render(request, 'event_planner/gift_search_detail.html', context)



# -------------------------------------------------------------
# Function-based view which creates gift contribution
# -------------------------------------------------------------
@login_required
def create_gift_contribution(request):
    if request.method == 'POST':
        form = GiftContributionForm(request.POST)
        if form.is_valid():
            gift_contribution = form.save(commit=False)
            gift_contribution.manager = request.user.userprofile
            gift_contribution.save()

            # Create gift search automatically
            if form.cleaned_data.get('create_gift_search'):
                gift_search = GiftSearch.objects.create(
                    title=gift_contribution.title,
                    purpose=f"Gift search for: {gift_contribution.title}",
                    donee=gift_contribution.donee,
                    deadline=gift_contribution.deadline,
                    created_by = request.user.userprofile,
                    is_auto_generated = True,
                )
                gift_contribution.gift_search = gift_search
                gift_contribution.save()

            messages.success(request, "Gift Contribution created successfully!")

            # Redirect to gift contribution list
            redirect_url = reverse('gift_contribution_list')
            return HttpResponse(
                f'<script type="text/javascript">window.top.location.href = "{redirect_url}";</script>'
            )
        else:
            # Iterate over each errors to add messages
            for field, error_list in form.errors.items():
                for error in error_list:
                    messages.error(request, f"{field.capitalize()}: {error}")

            messages.error(request, "Please correct the errors below.")
    else:
        form = GiftContributionForm()
    return render(request, 'event_planner/create_gift_contribution.html', {'form': form})



# -------------------------------------------------------------
# Function-based view which lists all open gift contributions
# -------------------------------------------------------------
@login_required
def gift_contribution_list(request):
    # Exclude contributions where user is donee, only open lists
    contributions = GiftContribution.objects.exclude(donee=request.user.userprofile).filter(status='open')
    for contribution in contributions:
        # Annotate whether the current user has already contributed
        contribution.user_contributed = contribution.contributions.filter(contributor=request.user.userprofile).exists()
        # Calculate progress percentage
        if contribution.collection_target:
            contribution.progress = "{:.0f}%".format((contribution.total_contributions() / contribution.collection_target) * 100)
        else:
            contribution.progress = 0

    return render(request, 'event_planner/gift_contribution_list.html', {
        'contributions': contributions,
        'today': date.today()
    })



# -------------------------------------------------------------
# Function-based view which lists all closed gift contributions (donee excluded)
# -------------------------------------------------------------
@login_required
def closed_contribution_list(request):
    today = timezone.now().date()
    # Exclude contributions where user is donee, only closed lists
    closed_contributions = GiftContribution.objects.filter(status__in=['closed', 'canceled']).exclude(donee=request.user.userprofile)
    for contribution in closed_contributions:
        # Calculate progress percentage
        if contribution.collection_target:
            contribution.progress = "{:.0f}%".format((contribution.total_contributions() / contribution.collection_target) * 100)
        else:
            contribution.progress = 0

        if contribution.gift_search:
            if contribution.gift_search.deadline <= today:
                search = contribution.gift_search
                proposals = search.proposals.all()
                best_proposal = None
                best_vote_count = -1
                # Find best voted proposal
                for proposal in proposals:
                    vote_count = proposal.votes.count()
                    if vote_count > best_vote_count:
                        best_vote_count = vote_count
                        best_proposal = proposal

                search.best_proposal=best_proposal
                search.vote_count=best_vote_count

    return render(request, 'event_planner/closed_contribution_list.html', {
        'closed_contributions': closed_contributions,
        'today': date.today()
    })



# -------------------------------------------------------------
# Function-based view which displays update functionality on gift contributions (only manager)
# -------------------------------------------------------------
@login_required
def update_gift_contribution(request):
    if request.method == 'POST':
        today = timezone.now().date()
        gc_id = request.POST.get('gift_contribution_id')
        gift_contribution = get_object_or_404(GiftContribution, id=gc_id)

        # Only manager can update
        if request.user.userprofile != gift_contribution.manager:
            return HttpResponseForbidden("You are not allowed to update this gift contribution.")
        
        # Update gift contribution
        new_deadline = request.POST.get('deadline')
        new_status = request.POST.get('status')
        if new_status == "closed" or new_status == "canceled":
            gift_contribution.deadline = today
        else:
            gift_contribution.deadline = new_deadline

        gift_contribution.status = new_status
        gift_contribution.save()

        # Update gift search
        # If status is canceled, set deadline to today and check booleans
        if gift_contribution.gift_search:
            gift_search_deadline = request.POST.get('gift_search_deadline')
            if new_status == 'canceled':
                gift_contribution.gift_search.deadline = today
                gift_contribution.gift_search.final_results_sent = True
                gift_contribution.gift_search.invitation_sent = True
                gift_contribution.gift_search.reminder_sent = True
            else:
                if gift_search_deadline:
                    gift_contribution.gift_search.deadline = gift_search_deadline
            gift_contribution.gift_search.save()
        
        messages.success(request, "Gift Contribution updated successfully!")
        # Back to parent window and close modal
        return HttpResponse(f"""
            <script>
                window.parent.postMessage({{ action: 'updateSuccess', modalId: 'updateModal{gift_contribution.id}' }}, '*');
            </script>
        """)
    
    else:
        # For GET requests, render the update form in a modal.
        gc_id = request.GET.get('gift_contribution_id')
        gift_contribution = get_object_or_404(GiftContribution, id=gc_id)
        return render(request, 'event_planner/update_gift_contribution_modal.html', {'gift': gift_contribution})



# -------------------------------------------------------------
# Function-based view which displays details of gift contribution
# -------------------------------------------------------------
@login_required
def gift_contribution_detail(request, pk):
    gift_contribution = get_object_or_404(GiftContribution, pk=pk)

    # Prevent donee from viewing this section
    if request.user.userprofile == gift_contribution.donee:
        return HttpResponseForbidden("You are not allowed to view this page.")
    
    total_amount = gift_contribution.total_contributions()
    num_contributors = gift_contribution.contribution_count()
    try:
        user_contribution = gift_contribution.contributions.get(contributor=request.user.userprofile)
    except Contribution.DoesNotExist:
        user_contribution = None
    return render(request, 'event_planner/gift_contribution_detail.html', {
        'gift_contribution': gift_contribution,
        'total_amount': total_amount,
        'num_contributors': num_contributors,
        'user_contribution': user_contribution,
    })



# -------------------------------------------------------------
# Function-based view which allows to contribute for a gift
# -------------------------------------------------------------
@login_required
def contribute_to_gift(request, pk):
    gift_contribution = get_object_or_404(GiftContribution, pk=pk)
    # Allow contributions if deadline has not passed
    if date.today() > gift_contribution.deadline:
        messages.error(request, "The deadline for this contribution has passed.")
        return redirect('gift_contribution_detail', pk=pk)
    
    # Prevent donee from viewing this section
    if request.user.userprofile == gift_contribution.donee:
        return HttpResponseForbidden("You are not allowed to contribute to your own gift.")
    
    try:
        contribution = gift_contribution.contributions.get(contributor=request.user.userprofile)
        if request.method == 'POST':
            form = ContributionForm(request.POST, instance=contribution)
            if form.is_valid():
                form.save()
                messages.success(request, "Your contribution has been updated.")
                # return redirect(f"{reverse('gift_contribution_detail', kwargs={'pk': pk})}?fireworks=1")

                return HttpResponse(f"""
                    <script>
                        window.parent.postMessage({{ action: 'contributionSuccess', modalId: 'contributionModal{pk}' }}, '*');
                    </script>
                """)
        else:
            form = ContributionForm(instance=contribution)

    except Contribution.DoesNotExist:
        if request.method == 'POST':
            form = ContributionForm(request.POST)
            if form.is_valid():
                new_contribution = form.save(commit=False)
                new_contribution.gift_contribution = gift_contribution
                new_contribution.contributor = request.user.userprofile
                new_contribution.save()
                messages.success(request, "Your contribution has been recorded.")
                #return redirect(f"{reverse('gift_contribution_detail', kwargs={'pk': pk})}?fireworks=1")

                return HttpResponse(f"""
                    <script>
                        window.parent.postMessage({{ action: 'contributionSuccess', modalId: 'contributionModal{pk}' }}, '*');
                    </script>
                """)
        else:
            form = ContributionForm()
    
    return render(request, 'event_planner/contribute_to_gift.html', {
        'form': form,
        'gift_contribution': gift_contribution,
    })



# -------------------------------------------------------------
# Function-based view which 
# -------------------------------------------------------------
@login_required
def list_gift_contributions(request, pk):
    gift_contribution = get_object_or_404(GiftContribution, pk=pk)

    # Only manager can view list of contributions
    if request.user.userprofile != gift_contribution.manager:
        return HttpResponseForbidden("You are not allowed to view this page.")
    
    contributions = gift_contribution.contributions.all()
    return render(request, 'event_planner/list_contributions.html', {
        'gift_contribution': gift_contribution,
        'contributions': contributions,
    })



# -------------------------------------------------------------
# Helper function to unwrap lazy object before passing it to the vote functions
# -------------------------------------------------------------
def unwrap_user(user):
    if isinstance(user, SimpleLazyObject):
        return user._wrapped
    return user


# -------------------------------------------------------------
# Function-based view which allows to vote for a gift proposal
# -------------------------------------------------------------
@login_required
def vote_gift_proposal(request, proposal_id, vote_type):
    proposal = get_object_or_404(GiftProposal, id=proposal_id)
    if proposal.gift_search.donee == request.user.userprofile:
        return redirect('gift_search_detail', search_id=proposal.gift_search.id)
    
    real_user = unwrap_user(request.user.id)
    
    if vote_type == 'up':
        proposal.votes.up(real_user)
    elif vote_type == 'down':
        proposal.votes.down(real_user)
    
    return redirect('gift_search_detail', search_id=proposal.gift_search.id)



# -------------------------------------------------------------
# Function-based view which allows to set parameters for jobs
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["GET", "POST"])
def role_configuration(request):
    # Dictionary mapping each role to its points
    role_config = {}
    for role in ['organizer', 'attendee', 'manager', 'honouree']:
        try:
            rc = RoleConfiguration.objects.get(role=role)
            role_config[role] = rc.points
        except RoleConfiguration.DoesNotExist:
            role_config[role] = 0

    for role in ['procurer', 'proposer', 'voter', 'winner']:
        try:
            rc = GiftConfiguration.objects.get(role=role)
            role_config[role] = rc.points
        except GiftConfiguration.DoesNotExist:
            role_config[role] = 0

    if request.method == "POST":
        form = RoleConfigurationForm(request.POST, role_config=role_config)
        if form.is_valid():
            form.save()
            return render(request, "event_planner/role_configuration_success.html")
        else:
            # If invalid, re-render the form with errors
            return render(request, "event_planner/role_configuration.html", {"form": form})
    else:
        form = RoleConfigurationForm(role_config=role_config)
        return render(request, "event_planner/role_configuration.html", {"form": form})
    


# -------------------------------------------------------------
# Function-based view which allows to set parameters for jobs
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["GET", "POST"])
def job_settings(request):
    if request.method == "POST":
        # Update JOB_CONFIG values from form submission
        # Overdue tasks settings
        JOB_CONFIG['check_overdue_tasks']['enabled'] = request.POST.get('check_overdue_enabled') == 'on'
        JOB_CONFIG['check_overdue_tasks']['interval'] = int(request.POST.get('check_overdue_interval', JOB_CONFIG['check_overdue_tasks']['interval']))

        # Task reminder email settings
        JOB_CONFIG['send_reminder_email']['enabled'] = request.POST.get('send_reminder_enabled') == 'on'
        JOB_CONFIG['send_reminder_email']['interval'] = int(request.POST.get('send_reminder_interval', JOB_CONFIG['send_reminder_email']['interval']))
        JOB_CONFIG['send_reminder_email']['lead_time'] = int(request.POST.get('send_reminder_lead_time', JOB_CONFIG['send_reminder_email']['lead_time']))

        # Event invitation email settings
        JOB_CONFIG['send_invitation_email']['enabled'] = request.POST.get('send_invitation_enabled') == 'on'
        JOB_CONFIG['send_invitation_email']['interval'] = int(request.POST.get('send_invitation_interval', JOB_CONFIG['send_invitation_email']['interval']))

        # Change event status settings
        JOB_CONFIG['update_event_status']['enabled'] = request.POST.get('update_event_enabled') == 'on'
        JOB_CONFIG['update_event_status']['interval'] = int(request.POST.get('update_event_interval', JOB_CONFIG['update_event_status']['interval']))

        # Gift search invitation email settings
        JOB_CONFIG['send_gift_search_invitation']['enabled'] = request.POST.get('send_gift_search_invitation_enabled') == 'on'
        JOB_CONFIG['send_gift_search_invitation']['interval'] = int(request.POST.get('send_gift_search_invitation_interval', JOB_CONFIG['send_gift_search_invitation']['interval']))

        # Gift search reminder email settings
        JOB_CONFIG['gift_search_reminder']['enabled'] = request.POST.get('gift_search_reminder_enabled') == 'on'
        JOB_CONFIG['gift_search_reminder']['interval'] = int(request.POST.get('gift_search_reminder_interval', JOB_CONFIG['gift_search_reminder']['interval']))
        JOB_CONFIG['gift_search_reminder']['lead_time'] = int(request.POST.get('gift_search_reminder_lead_time', JOB_CONFIG['gift_search_reminder']['lead_time']))

        # Gift results email settings
        JOB_CONFIG['gift_search_results']['enabled'] = request.POST.get('gift_search_enabled') == 'on'
        JOB_CONFIG['gift_search_results']['interval'] = int(request.POST.get('gift_search_interval', JOB_CONFIG['gift_search_results']['interval']))

        # Gift contribution invitation email settings
        JOB_CONFIG['send_gift_contribution_invitation']['enabled'] = request.POST.get('send_gift_contribution_invitation_enabled') == 'on'
        JOB_CONFIG['send_gift_contribution_invitation']['interval'] = int(request.POST.get('send_gift_contribution_invitation_interval', JOB_CONFIG['send_gift_contribution_invitation']['interval']))

        # Gift contribution reminder email settings
        JOB_CONFIG['gift_contribution_reminder']['enabled'] = request.POST.get('gift_contribution_reminder_enabled') == 'on'
        JOB_CONFIG['gift_contribution_reminder']['interval'] = int(request.POST.get('gift_contribution_reminder_interval', JOB_CONFIG['gift_contribution_reminder']['interval']))
        JOB_CONFIG['gift_contribution_reminder']['lead_time'] = int(request.POST.get('gift_contribution_reminder_lead_time', JOB_CONFIG['gift_contribution_reminder']['lead_time']))

        # Change contribution status settings
        JOB_CONFIG['update_contribution_status']['enabled'] = request.POST.get('update_contribution_enabled') == 'on'
        JOB_CONFIG['update_contribution_status']['interval'] = int(request.POST.get('update_contribution_interval', JOB_CONFIG['update_contribution_status']['interval']))

        # Birthday event settings
        JOB_CONFIG['create_birthday_event']['enabled'] = request.POST.get('create_birthday_enabled') == 'on'
        JOB_CONFIG['create_birthday_event']['interval'] = int(request.POST.get('create_birthday_interval', JOB_CONFIG['create_birthday_event']['interval']))
        JOB_CONFIG['create_birthday_event']['future_search_offset'] = int(request.POST.get('create_birthday_offset', JOB_CONFIG['create_birthday_event']['future_search_offset']))
        JOB_CONFIG['create_birthday_event']['min_users_required'] = int(request.POST.get('create_birthday_min_users', JOB_CONFIG['create_birthday_event']['min_users_required']))
        JOB_CONFIG['create_birthday_event']['max_users_allowed'] = int(request.POST.get('create_birthday_max_users', JOB_CONFIG['create_birthday_event']['max_users_allowed']))

        # Round birthday gift search settings
        JOB_CONFIG['create_round_birthday_gift_search']['enabled'] = request.POST.get('create_round_birthday_enabled') == 'on'
        JOB_CONFIG['create_round_birthday_gift_search']['interval'] = int(request.POST.get('create_round_birthday_interval', JOB_CONFIG['create_round_birthday_gift_search']['interval']))
        JOB_CONFIG['create_round_birthday_gift_search']['future_search_offset'] = int(request.POST.get('create_round_birthday_offset', JOB_CONFIG['create_round_birthday_gift_search']['future_search_offset']))
        JOB_CONFIG['create_round_birthday_gift_search']['deadline'] = int(request.POST.get('create_round_birthday_deadline', JOB_CONFIG['create_round_birthday_gift_search']['deadline']))

        # Payment reminder email settings
        JOB_CONFIG['check_payment_reminder']['enabled'] = request.POST.get('check_payment_enabled') == 'on'
        JOB_CONFIG['check_payment_reminder']['interval'] = int(request.POST.get('check_payment_interval', JOB_CONFIG['check_payment_reminder']['interval']))
        JOB_CONFIG['check_payment_reminder']['overdue_threshold'] = int(request.POST.get('check_payment_threshold', JOB_CONFIG['check_payment_reminder']['overdue_threshold']))

        # Store historical sser scores settings
        JOB_CONFIG['store_user_scores']['enabled'] = request.POST.get('store_scores_enabled') == 'on'
        JOB_CONFIG['store_user_scores']['interval'] = int(request.POST.get('store_scores_interval', JOB_CONFIG['store_user_scores']['interval']))

        # Persist changes to JSON file
        save_job_config(JOB_CONFIG)
        # Reschedule jobs
        schedule_jobs()
        # return redirect(request.META.get('HTTP_REFERER', '/'))
        return render(request, "event_planner/job_settings_success.html")
    else:
        return render(request, "event_planner/job_settings.html", {"job_config": JOB_CONFIG})
    


# -------------------------------------------------------------
# Function-based view which allows to set general parameters for jobs
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["GET", "POST"])
def general_settings(request):
    # Get configuration dictionaries
    config_score_interval = JOB_CONFIG.get('store_user_scores', {})
    config_general = JOB_CONFIG.get('general', {})

    if request.method == "POST":
        # Rank Change Interval for past scores (in days)
        try:
            new_interval = int(request.POST.get('rank_change_interval', config_score_interval.get('rank_change_interval', 30)))
        except (ValueError, TypeError):
            new_interval = config_score_interval.get('rank_change_interval', 30)
        # Clamp value between 1 and 365
        new_interval = max(1, min(new_interval, 365))
        config_score_interval['rank_change_interval'] = new_interval

        # Conversion Rate for payments (as a float)
        try:
            new_rate = float(request.POST.get('conversion_rate', config_general.get('conversion_rate', 0.5)))
        except (ValueError, TypeError):
            new_rate = config_general.get('conversion_rate', 0.5)
        config_general['conversion_rate'] = new_rate

        # Payment Penalty (as an integer, negative number expected)
        try:
            new_penalty = int(request.POST.get('payment_penalty', config_general.get('payment_penalty', -25)))
        except (ValueError, TypeError):
            new_penalty = config_general.get('payment_penalty', -25)
        config_general['payment_penalty'] = new_penalty

        # Persist changes to JSON file
        save_job_config(JOB_CONFIG)

        # Return success page that closes modal
        return render(request, "event_planner/general_settings_success.html")
    else:
        current_interval = config_score_interval.get('rank_change_interval', 30)
        description_interval = config_score_interval.get('description', '')
        current_rate = config_general.get('conversion_rate', 0.5)
        description_rate = config_general.get('description', '')
        current_penalty = config_general.get('payment_penalty', -25)
        description_penalty = config_general.get('description2', '')

        return render(request, "event_planner/general_settings.html", {
            "current_interval": current_interval, 
            "description_interval": description_interval,
            "current_rate": current_rate,
            "description_rate": description_rate,
            "current_penalty": current_penalty,
            "description_penalty": description_penalty,
        })



# -------------------------------------------------------------
# Function-based view which allows the admin to manager users
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
def user_management(request):
    # User list
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
            # Deletion of user
            if action == "delete":
                if target_user != request.user:
                    target_user.delete()
                    messages.success(request, f"User {target_user.username} deleted.")
                else:
                    messages.error(request, "You cannot delete yourself.")
            # Deactivation of user
            elif action == "deactivate":
                if target_user != request.user:
                    target_user.is_active = False
                    target_user.save()
                    messages.success(request, f"User {target_user.username} deactivated.")
                else:
                    messages.error(request, "You cannot deactivate yourself.")
            # Activation of user
            elif action == "activate":
                target_user.is_active = True
                target_user.save()
                messages.success(request, f"User {target_user.username} activated.")
            # User is staff (admin)
            elif action == "make_staff":
                if target_user != request.user:
                    target_user.is_staff = True
                    target_user.save()
                    messages.success(request, f"User {target_user.username} is now a staff member.")
                else:
                    messages.error(request, "You cannot change your own staff status.")
            # User is non-staff (non-admin)
            elif action == "remove_staff":
                if target_user != request.user:
                    target_user.is_staff = False
                    target_user.save()
                    messages.success(request, f"User {target_user.username} is no longer a staff member.")
                else:
                    messages.error(request, "You cannot change your own staff status.")
            else:
                messages.error(request, "Invalid action.")
        else:
            messages.error(request, "No user selected.")
        return redirect("user_management")
    
    # Search and sorting
    query = request.GET.get("q", "").strip()
    sort_field = request.GET.get("sort", "username")
    direction = request.GET.get("direction", "asc")
    
    users = User.objects.all()
    if query:
        # Filter by username or email (case-insensitive)
        users = users.filter(username__icontains=query) | users.filter(email__icontains=query)
    
    # Fields for sorting
    if sort_field not in ["username", "email", "is_active", "is_staff"]:
        sort_field = "username"
    if direction == "desc":
        sort_field = "-" + sort_field
    users = users.order_by(sort_field)
    
    context = {
        "users": users,
        "query": query,
        "current_sort": sort_field.lstrip("-"),
        "direction": direction,
    }
    return render(request, "event_planner/user_management.html", context)



# -------------------------------------------------------------
# Function-based view which allows the admin to manage gift contributions
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
def gift_contribution_management(request):
    # Process POST actions force_close, reopen, delete
    if request.method == 'POST':
        action = request.POST.get('action')
        gc_id = request.POST.get('gift_contribution_id')
        if gc_id:
            gift_contribution = GiftContribution.objects.get(id=gc_id)
            if action == 'delete':
                gift_contribution.delete()
                messages.success(request, f"Gift contribution '{gift_contribution.title}' deleted.")
            elif action == 'force_close':
                if gift_contribution.deadline > timezone.now().date():
                    gift_contribution.deadline = timezone.now().date()
                    gift_contribution.status = 'closed'
                    gift_contribution.save()
                    messages.success(request, f"Gift contribution '{gift_contribution.title}' force closed.")
                else:
                    messages.info(request, f"Gift contribution '{gift_contribution.title}' is already closed.")
            elif action == 'reopen':
                new_deadline = request.POST.get("new_deadline")
                if new_deadline:
                    try:
                        new_deadline_date = datetime.strptime(new_deadline, "%Y-%m-%d").date()
                    except ValueError:
                        messages.error(request, "Invalid date format.")
                        return redirect("gift_contribution_management")
                    if new_deadline_date <= timezone.now().date():
                        messages.error(request, "New deadline must be in the future.")
                    else:
                        gift_contribution.deadline = new_deadline_date
                        gift_contribution.status = 'open'
                        gift_contribution.save()
                        messages.success(request, f"Gift contribution '{gift_contribution.title}' reopened with new deadline {new_deadline_date}.")
                else:
                    messages.error(request, "Please provide a new deadline.")

            else:
                messages.error(request, "Invalid action.")

        else:
            messages.error(request, "No gift contribution selected.")
        return redirect('gift_contribution_management')
    
   # GET: Process search and sorting
    query = request.GET.get("q", "").strip()
    sort_field = request.GET.get("sort", "title")
    direction = request.GET.get("direction", "asc")
    
    gift_contributions = GiftContribution.objects.all()
    if query:
        gift_contributions = gift_contributions.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(donee__user__username__icontains=query) |
            Q(manager__user__username__icontains=query) |
            Q(status__icontains=query)
        )

    # Allow only specific fields for sorting
    if sort_field not in ["title", "deadline", "donee", "manager", "created_at"]:
        sort_field = "title"
    if direction == "desc":
        sort_field = "-" + sort_field
    gift_contributions = gift_contributions.order_by(sort_field)
    
    # Pass today's date to template for comparison
    today = timezone.now().date()

    context = {
        "gift_contributions": gift_contributions,
        "query": query,
        "current_sort": sort_field.lstrip("-"),
        "direction": direction,
        "today": today,
    }
    return render(request, 'event_planner/gift_contribution_management.html', context)



# -------------------------------------------------------------
# Function-based view which allows the admin to manage gift searches
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
def gift_search_management(request):
    # Process POST actions force_close, reopen, delete
    if request.method == "POST":
        action = request.POST.get("action")
        gs_id = request.POST.get("gift_search_id")
        if gs_id:
            gift_search = get_object_or_404(GiftSearch, id=gs_id)
            if action == "delete":
                gift_search.delete()
                messages.success(request, f"Gift search '{gift_search.title}' deleted.")
            elif action == "force_close":
                if gift_search.deadline > timezone.now().date():
                    gift_search.deadline = timezone.now().date()
                    gift_search.save()
                    messages.success(request, f"Gift search '{gift_search.title}' force closed.")
                else:
                    messages.info(request, f"Gift search '{gift_search.title}' is already closed.")
            elif action == "reopen":
                new_deadline = request.POST.get("new_deadline")
                if new_deadline:
                    try:
                        new_deadline_date = datetime.strptime(new_deadline, "%Y-%m-%d").date()
                    except ValueError:
                        messages.error(request, "Invalid date format.")
                        return redirect("gift_search_management")
                    if new_deadline_date <= timezone.now().date():
                        messages.error(request, "New deadline must be in the future.")
                    else:
                        gift_search.deadline = new_deadline_date
                        gift_search.save()
                        messages.success(request, f"Gift search '{gift_search.title}' reopened with new deadline {new_deadline_date}.")
                else:
                    messages.error(request, "Please provide a new deadline.")
            else:
                messages.error(request, "Invalid action.")
        else:
            messages.error(request, "No gift search selected.")
        return redirect("gift_search_management")
    
    # GET: Process search and sorting
    query = request.GET.get("q", "").strip()
    sort_field = request.GET.get("sort", "title")
    direction = request.GET.get("direction", "asc")
    
    gift_searches = GiftSearch.objects.all()
    if query:
        gift_searches = gift_searches.filter(
            Q(title__icontains=query) |
            Q(purpose__icontains=query) |
            Q(donee__user__username__icontains=query)
        )
    
    # Allow only specific fields for sorting
    if sort_field not in ["title", "deadline", "created_at"]:
        sort_field = "title"
    if direction == "desc":
        sort_field = "-" + sort_field
    gift_searches = gift_searches.order_by(sort_field)
    
    # Pass today's date to template for comparison
    today = timezone.now().date()
    
    context = {
        "gift_searches": gift_searches,
        "query": query,
        "current_sort": sort_field.lstrip("-"),
        "direction": direction,
        "today": today,
    }
    return render(request, "event_planner/gift_search_management.html", context)



# -------------------------------------------------------------
# Function-based view which allows the admin to manage events
# -------------------------------------------------------------
@user_passes_test(lambda u: u.is_staff)
@login_required
def event_management(request):
    if request.method == "POST":
        action = request.POST.get("action")
        event_id = request.POST.get("event_id")
        if event_id:
            event = get_object_or_404(Event, id=event_id)
            if action == "delete":
                event.delete()
                messages.success(request, f"Event '{event.title}' deleted.")
            elif action == "reschedule":
                new_date = request.POST.get("new_date")
                new_time = request.POST.get("new_time")
                if new_date and new_time:
                    try:
                        new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
                        new_time_obj = datetime.strptime(new_time, "%H:%M").time()
                    except ValueError:
                        messages.error(request, "Invalid date/time format.")
                        return redirect("event_management")
                    if new_date_obj < timezone.now().date():
                        messages.error(request, "New date must be in the future.")
                    else:
                        event.date = new_date_obj
                        event.time = new_time_obj
                        event.save()
                        messages.success(request, f"Event '{event.title}' rescheduled.")
                else:
                    messages.error(request, "Please provide both new date and new time.")
            elif action == "cancel":
                if event.status != 'canceled':
                    event.status = 'canceled'
                    event.save()
                    messages.success(request, f"Event '{event.title}' has been canceled.")
                else:
                    messages.info(request, f"Event '{event.title}' is already canceled.")
            else:
                messages.error(request, "Invalid action.")
        else:
            messages.error(request, "No event selected.")
        return redirect("event_management")
    
    # GET: Process search and sorting.
    query = request.GET.get("q", "").strip()
    sort_field = request.GET.get("sort", "title")
    direction = request.GET.get("direction", "asc")
    
    events = Event.objects.all()
    if query:
        events = events.filter(title__icontains=query) | events.filter(location__icontains=query)
    
    if sort_field not in ["title", "date", "time", "created_at"]:
        sort_field = "title"
    if direction == "desc":
        sort_field = "-" + sort_field
    events = events.order_by(sort_field)
    
    context = {
        "events": events,
        "query": query,
        "current_sort": sort_field.lstrip("-"),
        "direction": direction,
    }
    return render(request, "event_planner/event_management.html", context)





