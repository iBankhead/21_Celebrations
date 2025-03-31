import json
from collections import defaultdict
from decimal import Decimal
import pytest
from datetime import datetime, date
from decimal import Decimal
from datetime import date, timedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.http import Http404
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from event_planner.models import *
from event_planner import views


User = get_user_model()


# List of URL names with kwargs required to reverse the URL
# Note: For views that require an id, a dummy value is supplied (e.g. 1).
@pytest.mark.parametrize("url_name, kwargs", [
    ("index", {}),
    ("account_delete", {}),
    ("leaderboard", {}),
    ("event_list", {}),
    ("event_planned", {}),
    ("create_event", {}),
    ("edit_event_detail", {"event_id": 1}),
    ("add_role", {"event_id": 1}),
    ("delete_role", {"event_id": 1}),
    ("add_task", {"event_id": 1}),
    ("edit_task", {"event_id": 1}),
    ("get_task_data", {"event_id": 1, "task_id": 1}),
    ("delete_task", {"event_id": 1}),
    ("task_template_list", {}),
    ("create_task_template", {}),
    ("edit_task_template", {"template_id": 1}),
    ("delete_task_template", {"template_id": 1}),
    ("attend_event", {"event_id": 1}),
    ("decline_event", {"event_id": 1}),
    ("update_task_status", {"task_id": 1}),
    ("update_task_detail", {}),
    ("get_template_defaults", {"template_id": 1}),
    ("role_configuration", {}),
    ("job_settings", {}),
    ("general_settings", {}),
    ("personal_data", {}),
])





# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
# Helper function to create users with score values
# -------------------------------------------------------------
@pytest.fixture
def create_user_with_scores(db):
    def _create(username, role, role_past, task, task_past, gift, gift_past, is_inactive=False):
        user = User.objects.create_user(username=username, password='password')
        profile = user.userprofile
        profile.role_score = role
        profile.role_score_past = role_past
        profile.task_score = task
        profile.task_score_past = task_past
        profile.gift_score = gift
        profile.gift_score_past = gift_past
        profile.is_inactive = is_inactive
        profile.save()
        return user
    return _create

# -------------------------------------------------------------
# Helper function to create events for editing
# -------------------------------------------------------------
@pytest.fixture
def create_event(db, create_user_with_scores):
    def _create_event(user, title="Original Event", date_str="2025-05-05", description="Original description", event_type="birthday"):
        # Create simple event
        event = Event.objects.create(
            title=title,
            date=date_str,
            description=description,
            event_type=event_type,
            created_by=user
        )
        # Auto-assign creator as manager
        EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
        return event
    return _create_event

# -------------------------------------------------------------
# Helper function to create tasks for editing/deleting
# -------------------------------------------------------------
@pytest.fixture
def create_task(db):
    def _create_task(event, title="Test Task", description="Task description"):
        task = Task.objects.create(
            event=event,
            title=title,
            description=description,
            base_points=10,
            penalty_points=0,
            status="pending"
        )
        return task
    return _create_task

@pytest.fixture
def create_task_with_event(db, create_user_with_scores):
    def _create_task_with_event(user, status="pending"):
        event = Event.objects.create(
            title="Task event",
            date="2025-05-05",
            description="Task description",
            event_type="birthday",
            created_by=user
        )
        task = Task.objects.create(
            event=event,
            title="Test Task",
            description="Task description",
            base_points=10,
            penalty_points=0,
            status=status
        )
        task.assigned_to.add(user.userprofile)
        return task
    return _create_task_with_event

# -------------------------------------------------------------
# Helper function to create task_template
# -------------------------------------------------------------
@pytest.fixture
def create_task_template(db):
    def _create_task_template(title="Test Template", description="Test description", base_points=10, penalty_points=0, task_type="event"):
        return TaskTemplate.objects.create(
            title=title,
            description=description,
            base_points=base_points,
            penalty_points=penalty_points,
            task_type=task_type
        )
    return _create_task_template

# -------------------------------------------------------------
# Helper function to create gift_searches
# -------------------------------------------------------------
@pytest.fixture
def create_gift_search(db, create_user_with_scores):
    def _create_gift_search(user, title, deadline, donee):
        gs = GiftSearch.objects.create(
            title=title,
            purpose="Purpose",
            deadline=deadline,
            donee=donee,
            created_by=user.userprofile
        )
        return gs
    return _create_gift_search

# -------------------------------------------------------------
# Helper function to create transactions
# -------------------------------------------------------------
@pytest.fixture
def create_transaction(db):
    def _create_transaction(event, from_user, to_user, task, amount=10):
        return Transaction.objects.create(event=event, from_user=from_user.userprofile, to_user=to_user.userprofile, amount=amount, task=task)
    return _create_transaction




# -------------------------------------------------------------
# DASHBOARD/INDEX views
# -------------------------------------------------------------
# DASHBOARD: test view response
# -------------------------------------------------------------
@pytest.mark.django_db
def test_index_view_authenticated(client, django_user_model):
    # Create test user (Note: signal will automatically create UserProfile)
    test_user = django_user_model.objects.create_user(username='testuser', password='password')
    # Set UserProfile scores
    user_profile = test_user.userprofile
    user_profile.task_score = 20
    user_profile.role_score = 50
    user_profile.gift_score = 30
    user_profile.save()
    # Login user
    client.force_login(test_user)
    url = reverse('index')

    # Create event for tasks
    event_for_tasks = Event.objects.create(
        title="Task Event",
        date=timezone.now() + timedelta(days=1),
        description="Event for tasks",
        created_by=test_user
    )
    # Create event in future
    event_future = Event.objects.create(
        title="Future Event",
        date=timezone.now() + timedelta(days=2),
        description="A future event",
        created_by=test_user
    )
    # Create event in past
    event_past = Event.objects.create(
        title="Past Event",
        date=timezone.now() - timedelta(days=2),
        description="A past event",
        created_by=test_user
    )
    # Create open task and assign it to user profile
    task_open = Task.objects.create(
        event=event_for_tasks,
        title="Open Task",
        description="This task is open",
        base_points=10,
        penalty_points=-5,
        status="pending"
    )
    task_open.assigned_to.add(user_profile)
    # Create overdue task and assign it to user profile
    task_overdue = Task.objects.create(
        event=event_for_tasks,
        title="Overdue Task",
        description="This task is overdue",
        base_points=10,
        penalty_points=-5,
        due_date=timezone.now() - timedelta(days=2),
        status="overdue"
    )
    task_overdue.assigned_to.add(user_profile)
    # Create closed task and assign it to user profile
    task_closed = Task.objects.create(
        event=event_for_tasks,
        title="Closed Task",
        description="This task is closed",
        base_points=10,
        penalty_points=0,
        status="in progress"
    )
    task_closed.assigned_to.add(user_profile)
    task_closed.status="completed"
    task_closed.save()

    # Create RoleConfiguration entries
    RoleConfiguration.objects.create(role='manager', points=30)
    RoleConfiguration.objects.create(role='organizer', points=20)
    RoleConfiguration.objects.create(role='attendee', points=10)

    # Create event participations 
    role_manager = EventParticipant.objects.create(event=event_for_tasks, user_profile=user_profile, role='manager')
    role_organizer = EventParticipant.objects.create(event=event_for_tasks, user_profile=user_profile, role='organizer')
    role_attendee = EventParticipant.objects.create(event=event_future, user_profile=user_profile, role='attendee')

    # -------------------------------------------------------------
    # Call view and verify response
    # -------------------------------------------------------------
    response = client.get(url)
    assert response.status_code == 200
    # Check the template used
    templates = [t.name for t in response.templates]
    assert 'event_planner/index.html' in templates

    context = response.context
    # open_tasks should include open and overdue tasks
    open_tasks = context['open_tasks']
    assert task_open in open_tasks
    assert task_overdue in open_tasks
    assert task_closed not in open_tasks

    # upcoming_events include events with future date
    upcoming_events = context['upcoming_events']
    assert event_for_tasks in upcoming_events
    assert event_future in upcoming_events
    assert event_past not in upcoming_events

    # event_future has attribute "is_attending" set to False
    # event_future has attribute "is_attending" set to True
    for event in upcoming_events:
        if event.pk == event_for_tasks.pk:
            assert hasattr(event, 'is_attending')
            assert event.is_attending is False
        if event.pk == event_future.pk:
            assert hasattr(event, 'is_attending')
            assert event.is_attending is True

    # Role points set correctly from RoleConfiguration
    assert context['attendee_points'] == 10

    # current_points equal total_score
    assert context['current_points'] == user_profile.total_score

    # score_history contains entries and is sorted descending
    score_history = context['score_history']
    ids = [entry.pk for entry in score_history]
    role_score_manager = RoleScoreHistory.objects.get(event_participant=role_manager)
    role_score_organizer = RoleScoreHistory.objects.get(event_participant=role_organizer)
    role_score_attendee = RoleScoreHistory.objects.get(event_participant=role_attendee)
    task_score = TaskScoreHistory.objects.get(task=task_closed)
    assert role_score_manager.pk in ids
    assert role_score_organizer.pk in ids
    assert role_score_attendee.pk in ids
    assert task_score.pk in ids
    
    if len(score_history) >= 2:
        assert score_history[0].timestamp >= score_history[1].timestamp

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: GET request returns 400
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_get_returns_bad_request(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user)
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.get(url)

    assert response.status_code == 400
    assert b"Only POST requests are allowed" in response.content

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: POST request with missing status parameter
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_post_missing_status(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user) 
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.post(url, {}) 

    assert response.status_code == 400
    assert b"Invalid status" in response.content

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: POST request with invalid status
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_post_invalid_status(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user) 
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.post(url, {"status": "pending"})

    assert response.status_code == 400
    assert b"Invalid status" in response.content

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: valid POST with status 'in_progress'
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_post_valid_in_progress(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user) 
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.post(url, {"status": "in_progress"})

    # Redirect to dashboard (index)
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == "in_progress"
    expected_redirect = reverse('index')
    assert response.url == expected_redirect

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: valid POST with status 'completed'
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_post_valid_completed(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user, status="pending")
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.post(url, {"status": "completed"})

    # Redirect to dashboard (index)
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == "completed"
    expected_redirect = reverse('index')
    assert response.url == expected_redirect

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: POST request with task not assigned 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_task_not_assigned_returns_404(client, create_user_with_scores, create_task_with_event):
    # user A = owner of the task, user B = updater 
    user_a = create_user_with_scores("userA", 1, 0, 0, 0, 0, 0)
    user_b = create_user_with_scores("userB", 1, 0, 0, 0, 0, 0)
    client.force_login(user_b)
    task = create_task_with_event(user_a, status="pending")
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.post(url, {"status": "in_progress"})

    assert response.status_code == 404

# -------------------------------------------------------------
# DASHBOARD TASK STATUS: non-POST returns a 400
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_status_non_post_method(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    task = create_task_with_event(user, status="pending")
    url = reverse('update_task_status', kwargs={'task_id': task.id})
    response = client.put(url, {"status": "in_progress"})

    assert response.status_code == 400
    assert b"Only POST requests are allowed" in response.content

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: GET request returns 400
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_get_not_allowed(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    client.force_login(user)
    url = reverse('update_task_detail')
    response = client.get(url, {'task_id': task.id})

    assert response.status_code == 400
    assert "Only POST requests are allowed." in response.content.decode('utf-8')

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request missing task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_missing_task_id(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('update_task_detail')
    response = client.post(url, {})

    assert response.status_code == 400
    assert "Task ID is missing." in response.content.decode('utf-8')

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST with invalid task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_invalid_task_id(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('update_task_detail')
    response = client.post(url, {'task_id': '9999'})

    assert response.status_code == 404

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request task not assigned to user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_task_not_assigned(client, create_user_with_scores, create_task_with_event):
    creator = create_user_with_scores("creator", 1, 0, 0, 0, 0, 0)
    other = create_user_with_scores("other", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(creator, status="pending")
    client.force_login(other)
    url = reverse('update_task_detail')
    response = client.post(url, {'task_id': str(task.id)})

    assert response.status_code == 404

# # -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request with valid actual_expense
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_valid_actual_expenses(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    client.force_login(user)
    url = reverse('update_task_detail')
    valid_expenses = "100.50"
    response = client.post(url, {'task_id': str(task.id), 'actual_expenses': valid_expenses})

    # Redirect to index
    assert response.status_code == 302
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.actual_expenses == Decimal(valid_expenses)

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request with invalid actual_expenses
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_invalid_actual_expenses(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    client.force_login(user)
    url = reverse('update_task_detail')
    response = client.post(url, {'task_id': str(task.id), 'actual_expenses': 'invalid'})

    assert response.status_code == 400
    assert "Invalid value for actual expenses." in response.content.decode('utf-8')

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request with file upload 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_file_upload(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    client.force_login(user)
    url = reverse('update_task_detail')
    dummy_file = SimpleUploadedFile("test.txt", b"file content", content_type="text/plain")
    post_data = {
         'task_id': str(task.id),
         'attachment': dummy_file,

    }
    response = client.post(url, post_data)

    assert response.status_code == 302
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.attachment, "Task attachment should not be empty."
    assert updated_task.attachment.name.endswith('.txt'), f"Attachment name: {updated_task.attachment.name}"

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request with both actual_expenses and file upload
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_both_expenses_and_file(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    client.force_login(user)
    url = reverse('update_task_detail')
    valid_expenses = "50.00"
    dummy_file = SimpleUploadedFile("test.txt", b"file content", content_type="text/plain")
    post_data = {
         'task_id': str(task.id),
         'actual_expenses': valid_expenses,
         'attachment': dummy_file,
    }
    response = client.post(url, post_data)

    assert response.status_code == 302
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.actual_expenses == Decimal(valid_expenses)
    assert updated_task.attachment is not None
    assert updated_task.attachment.name.endswith('.txt'), f"Attachment name: {updated_task.attachment.name}"

# -------------------------------------------------------------
# DASHBOARD TASK DETAIL: POST request with no update fields
# -------------------------------------------------------------
@pytest.mark.django_db
def test_update_task_detail_no_update_fields(client, create_user_with_scores, create_task_with_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    task = create_task_with_event(user, status="pending")
    task.actual_expenses = Decimal("20.00")
    task.save()
    client.force_login(user)
    url = reverse('update_task_detail')
    response = client.post(url, {'task_id': str(task.id)})

    assert response.status_code == 302
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.actual_expenses == Decimal("20.00")

# -------------------------------------------------------------
# DASHBOARD ATTEND EVENT: anonymous GET redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_attend_event_redirects_anonymous_post(client, create_event, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('attend_event', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url.lower()

# -------------------------------------------------------------
# DASHBOARD ATTEND EVENT: GET request returns 400
# -------------------------------------------------------------
@pytest.mark.django_db
def test_attend_event_get_invalid_method(client, create_event, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('attend_event', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 400
    assert b"Invalid request method" in response.content

# -------------------------------------------------------------
# DASHBOARD ATTEND EVENT: valid POST request creates attendee record 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_attend_event_post_creates_attendee(client, create_event, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('attend_event', kwargs={'event_id': event.id})
    attendee_count_before = event.eventparticipant_set.filter(role='attendee').count()
    response = client.post(url, {})

    # Redirect to dashboard (index)
    assert response.status_code == 302
    expected_redirect = reverse('index')
    assert response.url == expected_redirect
    # attendee record has been created
    attendee_count_after = event.eventparticipant_set.filter(role='attendee').count()
    assert attendee_count_after == attendee_count_before + 1
    attendee_exists = event.eventparticipant_set.filter(user_profile=user.userprofile, role='attendee').exists()
    assert attendee_exists

# -------------------------------------------------------------
# DASHBOARD ATTEND EVENT: duplicate POST does not create duplicate attendee
# -------------------------------------------------------------
@pytest.mark.django_db
def test_attend_event_post_no_duplicate(client, create_event, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('attend_event', kwargs={'event_id': event.id})
    response1 = client.post(url, {})

    assert response1.status_code == 302
    count_after_first = event.eventparticipant_set.filter(role='attendee').count()
    # second POST
    response2 = client.post(url, {})
    assert response2.status_code == 302
    count_after_second = event.eventparticipant_set.filter(role='attendee').count()
    assert count_after_second == count_after_first

# -------------------------------------------------------------
# DASHBOARD ATTEND EVENT: POST request for non-existent event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_attend_event_post_nonexistent_event_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse('attend_event', kwargs={'event_id': non_existent_id})
    response = client.post(url, {})

    assert response.status_code == 404

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: anonymous GET redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_decline_event_redirects_anonymous_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("anonuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: anonymous POST request redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_decline_event_redirects_anonymous_post(client, create_user_with_scores, create_event):
    user = create_user_with_scores("anonuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: GET request returns 400
# -------------------------------------------------------------
# Test that a logged‑in GET request to decline_event returns a Bad Request (400).
@pytest.mark.django_db
def test_decline_event_get_bad_request(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 400
    assert "Invalid request method" in response.content.decode()

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: POST request with non‑existent event
# -------------------------------------------------------------
# Test that a POST request with a non‑existent event returns a 404.
@pytest.mark.django_db
def test_decline_event_nonexistent_event_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999 
    url = reverse('decline_event', kwargs={'event_id': non_existent_id})
    response = client.post(url, {})
    
    assert response.status_code == 404

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: POST request with no attendee record
# -------------------------------------------------------------
@pytest.mark.django_db
def test_decline_event_post_no_attendee_record(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    # create_event assigns manager
    event = create_event(user)
    # No attendee record should exists
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='attendee').count() == 0
    client.force_login(user)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert response.url == reverse('index')
    # manager record remains
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='manager').exists()

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: valid POST request
# -------------------------------------------------------------
@pytest.mark.django_db
def test_decline_event_post_removes_attendee_record(client, create_user_with_scores, create_event):
    # event creator = manager and attendee
    manager = create_user_with_scores("manager", 1, 0, 0, 0, 0, 0)
    attendee = create_user_with_scores("attendee", 1, 0, 0, 0, 0, 0)
    event = create_event(manager, title="Event for Decline Test")
    EventParticipant.objects.create(event=event, user_profile=attendee.userprofile, role='attendee')
    # attendee record exists
    assert event.eventparticipant_set.filter(user_profile=attendee.userprofile, role='attendee').exists()
    client.force_login(attendee)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert response.url == reverse('index')
    # attendee record was deleted
    assert not event.eventparticipant_set.filter(user_profile=attendee.userprofile, role='attendee').exists()

# -------------------------------------------------------------
# DASHBOARD DECLINE EVENT: other roles preserved
# -------------------------------------------------------------
@pytest.mark.django_db
def test_decline_event_preserves_manager_record(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user, title="Manager and Attendee")
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='attendee')
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='manager').exists()
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='attendee').exists()
    client.force_login(user)
    url = reverse('decline_event', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert response.url == reverse('index')
    # attendee record is removed, manager record remains
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='attendee').count() == 0
    assert event.eventparticipant_set.filter(user_profile=user.userprofile, role='manager').exists()



# -------------------------------------------------------------
# LEADERBOARD views
# -------------------------------------------------------------
# -------------------------------------------------------------
# Leaderboard: scores calculated correctly
# -------------------------------------------------------------
@pytest.mark.django_db
def test_computed_total_scores(create_user_with_scores):
    user = create_user_with_scores("compute_user", 4, 3, 5, 4, 2, 1)
    profile = user.userprofile
    assert profile.total_score == 4 + 5 + 2
    assert profile.total_score_past == 3 + 4 + 1

# -------------------------------------------------------------
# Leaderboard: template, context keys
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_template_and_context(client, create_user_with_scores):
    # Create user and view leaderboard
    user = create_user_with_scores("user_main", role=5, role_past=5, task=3, task_past=3, gift=2, gift_past=2)
    client.force_login(user)
    url = reverse("leaderboard")
    response = client.get(url)
    assert response.status_code == 200

    # Correct template is used
    templates = [t.name for t in response.templates]
    assert "event_planner/leaderboard.html" in templates

    # Context keys exist
    context = response.context
    context_keys = [
        "leaderboard_total",
        "leaderboard_roles",
        "leaderboard_tasks",
        "leaderboard_gifts",
        "historic_total_json",
        "historic_role_json",
        "historic_task_json",
        "historic_gift_json",
    ]
    for key in context_keys:
        assert key in context

# -------------------------------------------------------------
# Leaderboard: inactive users excluded
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_excludes_inactive_users(client, create_user_with_scores):
    # Create active and inactive user
    active_user = create_user_with_scores("active_user", role=5, role_past=5, task=3, task_past=3, gift=2, gift_past=2)
    inactive_user = create_user_with_scores("inactive_user", role=7, role_past=7, task=4, task_past=4, gift=3, gift_past=3, is_inactive=True)
    client.force_login(active_user)
    url = reverse("leaderboard")
    response = client.get(url)

    context = response.context
    # Lists built from active users only
    for key in ["leaderboard_total", "leaderboard_roles", "leaderboard_tasks", "leaderboard_gifts"]:
        leaderboard = context[key]
        for entry in leaderboard:
            assert entry["user"].is_inactive is False

# -------------------------------------------------------------
# Leaderboard: arrow computation based on current vs. past scores
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_arrow_computation(client, create_user_with_scores):
    # Create users with distinct score differences
    # current > past => arrow "up"
    user_up = create_user_with_scores("user_up", role=5, role_past=5, task=5, task_past=5, gift=5, gift_past=0)
    # current < past => arrow "down"
    user_down = create_user_with_scores("user_down", role=5, role_past=5, task=3, task_past=5, gift=0, gift_past=0)
    # current == past => arrow "right"
    user_right = create_user_with_scores("user_right", role=10, role_past=10, task=0, task_past=0, gift=0, gift_past=0)
    client.force_login(user_up)
    url = reverse("leaderboard")
    response = client.get(url)

    leaderboard_total = response.context["leaderboard_total"]
    # Create mapping from username to leaderboard entry
    entries = {entry["user"].user.username: entry for entry in leaderboard_total}
    assert entries["user_up"]["arrow"] == "up"
    assert entries["user_down"]["arrow"] == "down"
    assert entries["user_right"]["arrow"] == "right"

# -------------------------------------------------------------
# Leaderboard: ranking and rank_change calculation for total scores
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_ranking_and_rank_change(client, create_user_with_scores):
    # Create users with different total and past scores
    user_a = create_user_with_scores("user_a", role=5, role_past=3, task=5, task_past=3, gift=5, gift_past=2)
    user_b = create_user_with_scores("user_b", role=10, role_past=10, task=0, task_past=0, gift=0, gift_past=0)
    client.force_login(user_a)
    url = reverse("leaderboard")
    response = client.get(url)

    leaderboard_total = response.context["leaderboard_total"]
    # Create mapping from username to leaderboard entry
    entries = {entry["user"].user.username: entry for entry in leaderboard_total}
    # user_a: current_rank 1, previous_rank 2, rank_change = 1 
    assert entries["user_a"]["current_rank"] == 1
    assert entries["user_a"]["previous_rank"] == 2
    assert entries["user_a"]["rank_change"] == 1
    # user_b: current_rank 2, previous_rank 1, rank_change = -1
    assert entries["user_b"]["current_rank"] == 2
    assert entries["user_b"]["previous_rank"] == 1
    assert entries["user_b"]["rank_change"] == -1

# -------------------------------------------------------------
# Leaderboard: historic chart JSON structure
# -------------------------------------------------------------
@pytest.mark.django_db
def test_historic_chart_json_structure(client, create_user_with_scores):
    # Create user and some PastUserScores entries for current year
    user = create_user_with_scores("chart_user", role=5, role_past=5, task=3, task_past=3, gift=2, gift_past=2)
    current_year = date.today().year
    # Create two PastUserScores entries on different dates
    PastUserScores.objects.create(
        user=user,
        total_score=10,
        task_score=5,
        role_score=3,
        gift_score=2,
        score_date=date(current_year, 1, 15)
    )
    PastUserScores.objects.create(
        user=user,
        total_score=13,
        task_score=6,
        role_score=4,
        gift_score=3,
        score_date=date(current_year, 2, 15)
    )
    client.force_login(user)
    url = reverse("leaderboard")
    response = client.get(url)

    # Check historic JSON for total scores
    historic_total_json = response.context["historic_total_json"]
    data = json.loads(historic_total_json)
    assert "labels" in data
    assert "datasets" in data
    # Expect at least one label (dates from PastUserScores)
    assert len(data["labels"]) >= 1
    # Each dataset should have a label (username) and data array of same length as labels
    for dataset in data["datasets"]:
        assert "label" in dataset
        assert "data" in dataset
        assert len(dataset["data"]) == len(data["labels"])

# -------------------------------------------------------------
# Leaderboard: data for roles, tasks, gifts
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_other_categories(client, create_user_with_scores):
    # Create users with distinct scores for role, task, and gift
    user1 = create_user_with_scores("user1", role=7, role_past=5, task=4, task_past=2, gift=3, gift_past=3)
    user2 = create_user_with_scores("user2", role=5, role_past=7, task=2, task_past=4, gift=4, gift_past=2)
    client.force_login(user1)
    url = reverse("leaderboard")
    response = client.get(url)

    # For each leaderboard type check the expected keys
    for key in ["leaderboard_roles", "leaderboard_tasks", "leaderboard_gifts"]:
        leaderboard = response.context[key]
        for entry in leaderboard:
            for expected_key in ["user", "current_rank", "previous_rank", "rank_change", "arrow"]:
                assert expected_key in entry

        # First entry current_rank is 1
        if leaderboard:
            assert leaderboard[0]["current_rank"] == 1

# -------------------------------------------------------------
# Leaderboard: computed fields extended
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_computed_total_in_ranking(client, create_user_with_scores):
    # Create users with scores
    user_a = create_user_with_scores("user_a", 7, 2, 4, 3, 4, 3)
    user_b = create_user_with_scores("user_b", 3, 4, 3, 3, 4, 3)
    client.force_login(user_a)
    url = reverse("leaderboard")
    response = client.get(url)

    leaderboard_total = response.context["leaderboard_total"]
    # Create mapping from username to leaderboard entry
    entries = {entry["user"].user.username: entry for entry in leaderboard_total}
    # For past ranking, sorting by total_score_past descending
    assert entries["user_a"]["current_rank"] == 1
    assert entries["user_a"]["previous_rank"] == 2
    assert entries["user_a"]["rank_change"] == 1
    assert entries["user_b"]["current_rank"] == 2
    assert entries["user_b"]["previous_rank"] == 1
    assert entries["user_b"]["rank_change"] == -1

# -------------------------------------------------------------
# Leaderboard: no historic data)
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_no_past_scores(client, create_user_with_scores):
    # Create user with scores
    user = create_user_with_scores("nopast_user", 5, 5, 3, 3, 2, 2)
    client.force_login(user)
    url = reverse("leaderboard")
    response = client.get(url)

    # Historic chart JSON should be built from an empty queryset
    for key in ["historic_total_json", "historic_role_json", "historic_task_json", "historic_gift_json"]:
        historic_json = response.context[key]
        data = json.loads(historic_json)
        # When no PastUserScores exist, grouping yields empty lists
        assert data["labels"] == []
        assert data["datasets"] == []

# -------------------------------------------------------------
# Leaderboard: all active profiles have identical scores
# -------------------------------------------------------------
@pytest.mark.django_db
def test_leaderboard_all_equal_scores(client, create_user_with_scores):
    # Create two users with the same scores
    user1 = create_user_with_scores("equal1", 4, 4, 3, 3, 2, 2)
    user2 = create_user_with_scores("equal2", 4, 4, 3, 3, 2, 2)
    client.force_login(user1)
    url = reverse("leaderboard")
    response = client.get(url)

    # In this case, every score is the same
    leaderboard_total = response.context["leaderboard_total"]
    for entry in leaderboard_total:
        # Since current equals past, arrow should be "right"
        assert entry["arrow"] == "right"
        # With all equal scores, they should tie, so both get the same rank
        assert entry["current_rank"] == 1
        assert entry["previous_rank"] == 1
        # Rank change should be 0
        assert entry["rank_change"] == 0



# -------------------------------------------------------------
# EVENT views
# -------------------------------------------------------------
# -------------------------------------------------------------
# EVENT UPCOMING: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_redirects_anonymous(client):
    url = reverse('event_list')
    response = client.get(url)
    
    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT UPCOMING: GET request returns correct template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_get_returns_context_and_template(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Test Event", date_str="2025-10-05")
    url = reverse('event_list')
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert "event_planner/event_list.html" in templates
    assert "events" in response.context
    events = list(response.context["events"])
    assert event in events

# -------------------------------------------------------------
# EVENT UPCOMING: GET request returns events with date >= today
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_only_future_events(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    today = timezone.now().date()
    future_date = (today + timedelta(days=10)).isoformat()
    past_date = (today - timedelta(days=10)).isoformat()
    future_event = create_event(user, title="Future Event", date_str=future_date)
    past_event = create_event(user, title="Past Event", date_str=past_date)
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    assert future_event in events
    assert past_event not in events

# -------------------------------------------------------------
# EVENT UPCOMING: GET request returns event from today
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_includes_today_event(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    today_str = timezone.now().date().isoformat()
    today_event = create_event(user, title="Today Event", date_str=today_str)
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    assert today_event in events

# -------------------------------------------------------------
# EVENT UPCOMING: GET request orders events ascending
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_ordering(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    today = timezone.now().date()
    event1 = create_event(user, title="Event 1", date_str=(today + timedelta(days=5)).isoformat())
    event2 = create_event(user, title="Event 2", date_str=(today + timedelta(days=3)).isoformat())
    event3 = create_event(user, title="Event 3", date_str=(today + timedelta(days=7)).isoformat())
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    dates = [event.date for event in events]
    assert dates == sorted(dates)

# -------------------------------------------------------------
# EVENT UPCOMING: GET request is empty with no events upcoming
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_no_events(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    assert events == []

# -------------------------------------------------------------
# EVENT UPCOMING: only manager can edit event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_can_edit_true(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    # Creator is auto-assigned as manager
    event = create_event(user, title="Editable Event")
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    for evt in events:
        if evt.id == event.id:
            assert evt.can_edit is True

# -------------------------------------------------------------
# EVENT UPCOMING: users who are not managers cannot edit event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_can_edit_false(client, create_user_with_scores, create_event):
    creator = create_user_with_scores("creator", 1, 0, 0, 0, 0, 0)
    other = create_user_with_scores("other", 1, 0, 0, 0, 0, 0)
    # Creator is auto-assigned as manager
    event = create_event(creator, title="Non-editable for other")
    client.force_login(other)
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    for evt in events:
        if evt.id == event.id:
            assert evt.can_edit is False

# -------------------------------------------------------------
# EVENT UPCOMING: User can see all upcoming events
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_list_includes_events_from_all_users(client, create_user_with_scores, create_event):
    user1 = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user1)
    event1 = create_event(user1, title="User1 Event")
    event2 = create_event(user2, title="User2 Event")
    url = reverse('event_list')
    response = client.get(url)

    events = list(response.context["events"])
    # Both events appear in list
    assert event1 in events
    assert event2 in events

# -------------------------------------------------------------
# EVENT PLANNED: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_redirects_anonymous_get(client):
    url = reverse('event_planned')
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT PLANNED: user with no planned events sees empty list
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_get_empty(client, create_user_with_scores):
    user = create_user_with_scores("empty_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('event_planned')
    response = client.get(url)

    assert response.status_code == 200
    # Events list should be empty
    assert list(response.context.get('events')) == []

# -------------------------------------------------------------
# EVENT PLANNED: only events with date=None are included
# -------------------------------------------------------------
def test_event_planned_filters_by_date(client, create_user_with_scores, create_event):
    user = create_user_with_scores("filter_date_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    planned_event = Event.objects.create(
        title="Planned Event",
        date=None,
        description="Description",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=planned_event, user_profile=user.userprofile, role='manager')
    non_planned_event = create_event(user, title="Non-Planned Event", date_str="2025-05-05", description="Not planned")
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    assert planned_event in events
    assert non_planned_event not in events

# -------------------------------------------------------------
# EVENT PLANNED: only events with allowed roles are returned
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_allowed_roles(client, create_user_with_scores, create_event):
    user = create_user_with_scores("role_filter_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    allowed_event = Event.objects.create(
        title="Allowed Event",
        date=None,
        description="Allowed event",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=allowed_event, user_profile=user.userprofile, role='manager')
    disallowed_event = Event.objects.create(
        title="Disallowed Event",
        date=None,
        description="Disallowed event",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=disallowed_event, user_profile=user.userprofile, role='attendee')
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    assert allowed_event in events
    assert disallowed_event not in events

# -------------------------------------------------------------
# EVENT PLANNED: events ordered by title
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_ordering(client, create_user_with_scores):
    user = create_user_with_scores("ordering_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    titles = ["Zeta Event", "Alpha Event", "Beta Event"]
    events_created = []
    for t in titles:
        event = Event.objects.create(
            title=t,
            date=None,
            description=f"Description for {t}",
            event_type="birthday",
            created_by=user
        )
        EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
        events_created.append(event)
    url = reverse('event_planned')
    response = client.get(url)

    events = list(response.context.get('events'))
    sorted_titles = sorted(titles)
    returned_titles = [event.title for event in events]
    assert returned_titles == sorted_titles

# -------------------------------------------------------------
# EVENT PLANNED: duplicate events not returned
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_distinct(client, create_user_with_scores):
    user = create_user_with_scores("distinct_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = Event.objects.create(
        title="Distinct Event",
        date=None,
        description="Distinct event",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='organizer')
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    # Event should appear once
    assert len([e for e in events if e.id == event.id]) == 1

# -------------------------------------------------------------
# EVENT PLANNED: only manager can delete event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_can_delete_true(client, create_user_with_scores):
    user = create_user_with_scores("delete_true_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = Event.objects.create(
        title="Deletable Event",
        date=None,
        description="Description",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    # Find event and check can_delete
    for ev in events:
        if ev.id == event.id:
            assert getattr(ev, 'can_delete', False) is True

# -------------------------------------------------------------
# EVENT PLANNED: user not manager cannot delete event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_can_delete_false(client, create_user_with_scores):
    user = create_user_with_scores("delete_false_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = Event.objects.create(
        title="Non-deletable Event",
        date=None,
        description="Description",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='organizer')
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    for ev in events:
        if ev.id == event.id:
            assert getattr(ev, 'can_delete', True) is False

# -------------------------------------------------------------
# EVENT PLANNED: events belonging to different users are isolated
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_isolated_per_user(client, create_user_with_scores):
    user1 = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    # Event for user1
    event1 = Event.objects.create(
        title="User1 Event",
        date=None,
        description="Event for user1",
        event_type="birthday",
        created_by=user1
    )
    EventParticipant.objects.create(event=event1, user_profile=user1.userprofile, role='manager')
    # Event for user2
    event2 = Event.objects.create(
        title="User2 Event",
        date=None,
        description="Event for user2",
        event_type="birthday",
        created_by=user2
    )
    EventParticipant.objects.create(event=event2, user_profile=user2.userprofile, role='manager')
    # Log in as user1
    client.force_login(user1)
    url = reverse('event_planned')
    response = client.get(url)

    events = response.context.get('events')
    event_ids = [e.id for e in events]
    assert event1.id in event_ids
    assert event2.id not in event_ids

# -------------------------------------------------------------
# EVENT PLANNED: view uses correct template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_template(client, create_user_with_scores, create_event):
    user = create_user_with_scores("template_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = Event.objects.create(
        title="Template Event",
        date=None,
        description="Template test",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
    url = reverse('event_planned')
    response = client.get(url)

    templates = [t.name for t in response.templates]
    assert 'event_planner/event_planned.html' in templates

# -------------------------------------------------------------
# EVENT PLANNED: view uses correct context
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_planned_context_structure(client, create_user_with_scores, create_event):
    user = create_user_with_scores("context_user", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = Event.objects.create(
        title="Context Event",
        date=None,
        description="Testing context",
        event_type="birthday",
        created_by=user
    )
    EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='manager')
    url = reverse('event_planned')
    response = client.get(url)

    context = response.context
    assert 'events' in context
    for ev in context['events']:
        assert hasattr(ev, 'can_delete')

# -------------------------------------------------------------
# EVENT PLANNED DELETE: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_redirects_anonymous_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('delete_event', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT PLANNED DELETE: POST request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_redirects_anonymous_post(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('delete_event', kwargs={'event_id': event.id})
    response = client.post(url, {'confirm': 'yes'})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT PLANNED DELETE: GET request returns confirmation page
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_get_returns_confirmation_page(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event To Delete")
    url = reverse('delete_event', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/delete_event_confirm.html' in templates
    # Context includes event and form
    assert 'event' in response.context
    assert response.context['event'].id == event.id
    assert 'form' in response.context

# -------------------------------------------------------------
# EVENT PLANNED DELETE: valid POST request deletes event and redirects to event_planned
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_post_valid_deletes_event(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event To Delete")
    url = reverse('delete_event', kwargs={'event_id': event.id})
    valid_data = {
        'confirm': 'DEL'
    }
    response = client.post(url, valid_data)

    # Redirect to 'event_planned'
    assert response.status_code == 302
    expected_redirect = reverse('event_planned')
    assert response.url == expected_redirect
    # Event is deleted
    assert Event.objects.filter(id=event.id).count() == 0

# -------------------------------------------------------------
# EVENT PLANNED DELETE: invalid POST does not delete event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_post_invalid_not_delete_event(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event Not To Delete")
    url = reverse('delete_event', kwargs={'event_id': event.id})
    invalid_data = {
        'confirm': ''
    }
    response = client.post(url, invalid_data)

    # Rerender confirmation page
    assert response.status_code == 200
    assert Event.objects.filter(id=event.id).exists()

# -------------------------------------------------------------
# EVENT PLANNED DELETE: non-existent event returns 404
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_nonexistent_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse('delete_event', kwargs={'event_id': non_existent_id})
    response = client.get(url)

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT PLANNED DELETE: GET request does not delete event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_event_get_does_not_delete_event(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event To Delete")
    url = reverse('delete_event', kwargs={'event_id': event.id})
    event_count_before = Event.objects.count()
    response = client.get(url)

    # Rerender confirmation page
    assert response.status_code == 200
    assert Event.objects.filter(id=event.id).exists()
    assert Event.objects.count() == event_count_before

# -------------------------------------------------------------
# EVENT FINAL: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_redirects_anonymous_get(client):
    url = reverse('event_final')
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT FINAL: GET request returns correct context
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_get_returns_context(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Final Event", date_str="2025-06-01", description="For final view")
    event.status = 'completed'
    event.save()
    url = reverse('event_final')
    response = client.get(url)

    assert response.status_code == 200
    # Context contains 'events'
    assert 'events' in response.context
    # Event appears for manager
    events = response.context['events']
    assert event in events

# -------------------------------------------------------------
# EVENT FINAL: events with correct status
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_filters_by_status(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    accepted_event = create_event(user, title="Accepted Event", date_str="2025-06-02")
    accepted_event.status = 'billed'
    accepted_event.save()
    rejected_event = create_event(user, title="Rejected Event", date_str="2025-06-03")
    rejected_event.status = 'planned'
    rejected_event.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    assert accepted_event in events
    assert rejected_event not in events

# -------------------------------------------------------------
# EVENT FINAL: events where user is manager appear
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_filters_by_manager_role(client, create_user_with_scores, create_event):
    manager = create_user_with_scores("manager", 1, 0, 0, 0, 0, 0)
    other = create_user_with_scores("other", 1, 0, 0, 0, 0, 0)
    event = create_event(manager, title="Manager Event", date_str="2025-06-04")
    event.status = 'completed'
    event.save()
    # Log in as other user (not manager)
    client.force_login(other)
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    assert event not in events

# -------------------------------------------------------------
# EVENT FINAL: events ordered descending by date
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_order_by_date_descending(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event1 = create_event(user, title="Event 1", date_str="2025-06-10")
    event1.status = 'completed'
    event1.save()
    event2 = create_event(user, title="Event 2", date_str="2025-06-15")
    event2.status = 'paid'
    event2.save()
    url = reverse('event_final')
    response = client.get(url)

    events = list(response.context['events'])
    assert events[0].id == event2.id
    assert events[1].id == event1.id

# -------------------------------------------------------------
# EVENT FINAL: cost calculation is zero with no cost-related tasks
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_calculates_costs_no_tasks(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="No Cost Event", date_str="2025-06-20")
    event.status = 'completed'
    event.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    assert len(events) > 0
    for ev in events:
        if ev.id == event.id:
            assert ev.total_actual == 0
            assert ev.total_budget == 0
            assert ev.deviation == 0

# -------------------------------------------------------------
# EVENT FINAL: cost calculation is correct with cost-related tasks
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_calculates_costs_with_tasks(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Cost Event", date_str="2025-06-25")
    event.status = 'completed'
    event.save()
    task1 = create_task(event, title="Task 1")
    task1.is_cost_related = True
    task1.budget = 100
    task1.actual_expenses = 90
    task1.save()
    task2 = create_task(event, title="Task 2")
    task2.is_cost_related = True
    task2.budget = 50
    task2.actual_expenses = 60
    task2.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    for ev in events:
        if ev.id == event.id:
            assert ev.total_budget == 150
            assert ev.total_actual == 150  # 90 + 60
            assert ev.deviation == 0       # 150 - 150

# -------------------------------------------------------------
# EVENT FINAL: event.can_bill is set when status is 'completed'
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_can_bill_for_completed(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Completed Event", date_str="2025-06-30")
    event.status = 'completed'
    event.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    for ev in events:
        if ev.id == event.id:
            assert hasattr(ev, 'can_bill')
            assert ev.can_bill is True

# -------------------------------------------------------------
# EVENT FINAL: event.see_trans is set when status is 'billed' or 'paid'
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_see_trans_for_billed_paid(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event_billed = create_event(user, title="Billed Event", date_str="2025-07-05")
    event_billed.status = 'billed'
    event_billed.save()
    event_paid = create_event(user, title="Paid Event", date_str="2025-07-10")
    event_paid.status = 'paid'
    event_paid.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    for ev in events:
        if ev.id in [event_billed.id, event_paid.id]:
            assert hasattr(ev, 'see_trans')
            assert ev.see_trans is True

# -------------------------------------------------------------
# EVENT FINAL: cost values calculated correct when cost fields are missing 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_final_tasks_missing_cost_fields(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="No Cost Data Event", date_str="2025-07-20")
    event.status = 'completed'
    event.save()
    task = create_task(event, title="Task Without Cost Data")
    task.is_cost_related = True
    task.budget = None
    task.actual_expenses = None
    task.save()
    url = reverse('event_final')
    response = client.get(url)

    events = response.context['events']
    for ev in events:
        if ev.id == event.id:
            # Sums should be 0 if values are None.
            assert ev.total_budget == 0
            assert ev.total_actual == 0
            assert ev.deviation == 0

# -------------------------------------------------------------
# EVENT TRANSACTIONS: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_redirects_anonymous_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("anon_test", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    login_url = settings.LOGIN_URL
    assert login_url in response.url

# -------------------------------------------------------------
# EVENT TRANSACTIONS: POST request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_redirects_anonymous_post(client, create_user_with_scores, create_event):
    user = create_user_with_scores("anon_test", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    login_url = settings.LOGIN_URL
    assert login_url in response.url

# -------------------------------------------------------------
# EVENT TRANSACTIONS: GET request returns the correct template and context
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_get_returns_context(client, create_user_with_scores, create_event):
    user = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Transaction Event")
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert "event_planner/event_transactions.html" in templates
    context = response.context
    assert "event" in context
    assert "transactions" in context
    assert "now" in context
    assert context["event"].id == event.id
    assert isinstance(context["now"], datetime)

# -------------------------------------------------------------
# EVENT TRANSACTIONS: transactions list is empty with no transactions
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_no_transactions(client, create_user_with_scores, create_event):
    user = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="No Transaction Event")
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.get(url)

    transactions = response.context["transactions"]
    assert transactions.count() == 0

# -------------------------------------------------------------
# EVENT TRANSACTIONS: only transactions for given event are returned
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_filters_by_event(client, create_user_with_scores, create_event, create_transaction):
    user1 = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user1)
    event1 = create_event(user1, title="Event One")
    event2 = create_event(user2, title="Event Two")
    task = Task.objects.create(
        event=event1,
        title="Dummy Task",
        description="For transaction",
        base_points=10,
        penalty_points=0,
        status="pending"
    )
    # Transactions for event1 
    tx1 = create_transaction(event1, from_user=user1, to_user=user2, task=task, amount=20)

    task2 = Task.objects.create(
        event=event2,
        title="Dummy Task 2",
        description="For transaction",
        base_points=10,
        penalty_points=0,
        status="pending"
    )
    # Transactions for event2
    tx2 = create_transaction(event2, from_user=user2, to_user=user1, task=task2, amount=15)
    url = reverse("event_transactions", kwargs={'event_id': event1.id})
    response = client.get(url)

    transactions = response.context["transactions"]
    assert transactions.count() == 1
    assert transactions.first().id == tx1.id

# -------------------------------------------------------------
# EVENT TRANSACTIONS: transactions list is empty without transactions
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_no_transactions(client, create_user_with_scores, create_event):
    user = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="No Transaction Event")
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.get(url)

    transactions = response.context["transactions"]
    assert transactions.count() == 0

# -------------------------------------------------------------
# EVENT TRANSACTIONS: only transactions for given event are returned
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_filters_by_event(client, create_user_with_scores, create_event, create_transaction):
    user1 = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user1)
    event1 = create_event(user1, title="Event One")
    event2 = create_event(user2, title="Event Two")

    task = Task.objects.create(
        event=event1,
        title="Dummy Task",
        description="For transaction",
        base_points=10,
        penalty_points=0,
        status="pending"
    )
    # Transactions for event1
    tx1 = create_transaction(event1, from_user=user1, to_user=user2, task=task, amount=20)
    task2 = Task.objects.create(
        event=event2,
        title="Dummy Task 2",
        description="For transaction",
        base_points=10,
        penalty_points=0,
        status="pending"
    )
    # Transactions for event2
    tx2 = create_transaction(event2, from_user=user2, to_user=user1, task=task2, amount=15)
    url = reverse("event_transactions", kwargs={'event_id': event1.id})
    response = client.get(url)

    transactions = response.context["transactions"]
    assert transactions.count() == 1
    assert transactions.first().id == tx1.id

# -------------------------------------------------------------
# EVENT TRANSACTIONS: multiple transactions ordered by from_user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_ordering(client, create_user_with_scores, create_event, create_transaction):
    user1 = create_user_with_scores("alice", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("bob", 1, 0, 0, 0, 0, 0)
    client.force_login(user1)
    event = create_event(user1, title="Ordering Event")
    from event_planner.models import Task
    task = Task.objects.create(
        event=event,
        title="Ordering Task",
        description="For ordering",
        base_points=10,
        penalty_points=0,
        status="pending"
    )
    tx1 = create_transaction(event, from_user=user2, to_user=user1, task=task, amount=10)
    tx2 = create_transaction(event, from_user=user1, to_user=user2, task=task, amount=20)
    url = reverse("event_transactions", kwargs={'event_id': event.id})
    response = client.get(url)

    transactions = list(response.context["transactions"])
    assert transactions[0].from_user.user.username == "alice"
    assert transactions[1].from_user.user.username == "bob"

# -------------------------------------------------------------
# EVENT TRANSACTIONS: view returns 404 for a non-existent event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_event_transactions_nonexistent_event_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("user404", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse("event_transactions", kwargs={'event_id': non_existent_id})
    response = client.get(url)

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT CLEARING: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_redirects_anonymous_get(client, create_event, create_task, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT CLEARING: POST request by anonymous user
# -------------------------------------------------------------
# Test that anonymous POST requests to clearing_view are redirected.
@pytest.mark.django_db
def test_clearing_view_redirects_anonymous_post(client, create_event, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT CLEARING: GET request renders clearing form
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_get_renders_form(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    task = create_task(event, title="Cost Task")
    task.budget = 100
    task.actual_expenses = 80
    task.save()
    client.force_login(user)
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert "event_planner/clearing_form.html" in templates

# -------------------------------------------------------------
# EVENT CLEARING: bill_transactions data valid
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_bill_transactions_valid(client, monkeypatch, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task1 = create_task(event, title="Task 1")
    task1.actual_expenses = 50
    task1.budget = 60
    task1.save()
    task2 = create_task(event, title="Task 2")
    task2.actual_expenses = 30
    task2.budget = 40
    task2.save()
    payer_dict = {task1.id: user.userprofile.id, task2.id: user.userprofile.id}
    honoree_ids = [user.userprofile.id]
    # payer_data is encoded as utf-8, decoded with unicode_escape
    payer_data_json = json.dumps(payer_dict, cls=DjangoJSONEncoder)
    honoree_data_json = json.dumps(honoree_ids)
    post_data = {
        "action": "bill_transactions",
        "payer_data": payer_data_json,
        "honoree_data": honoree_data_json,
        "send_mail": "on"
    }
    # Monkeypatch send_billing_email to dummy function
    def dummy_send_billing_email(user_profile, event, payer_dict, division_results, transactions):
        return
    monkeypatch.setattr(views, "send_billing_email", dummy_send_billing_email)
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.post(url, post_data)

    # Redirect to "event_final"
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.status == "billed"

# -------------------------------------------------------------
# EVENT CLEARING: bill_transactions with invalid JSON
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_bill_transactions_invalid_json(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Task 1")
    task.actual_expenses = 50
    task.budget = 60
    task.save()
    # Invalid JSON
    post_data = {
        "action": "bill_transactions",
        "payer_data": "invalid json",
        "honoree_data": "[1]" 
    }
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.post(url, post_data)

    # Redirect to clearing_view
    assert response.status_code == 302
    messages = list(get_messages(response.wsgi_request))
    error = any("Error parsing payer data" in m.message for m in messages)
    assert error

# -------------------------------------------------------------
# EVENT CLEARING: no honorees selected
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_post_no_honorees(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Task No Honorees")
    task.actual_expenses = 40
    task.budget = 50
    task.save()
    post_data = {
        "action": "clear",
        f"task_{task.id}_payer": str(user.userprofile.id),
    }
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.post(url, post_data)

    assert response.status_code == 302
    messages = list(get_messages(response.wsgi_request))
    error_found = any("Please select at least one honoree" in m.message for m in messages)
    assert error_found

# -------------------------------------------------------------
# EVENT CLEARING: valid POST for clearing
# -------------------------------------------------------------
@pytest.mark.django_db
def test_clearing_view_post_valid_else_branch(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Valid Task")
    task.actual_expenses = 100
    task.budget = 120
    task.save()
    post_data = {
        "action": "clear",
        f"task_{task.id}_payer": str(user.userprofile.id),
        "honorees": [str(user.userprofile.id)]
    }
    url = reverse("clearing_view", kwargs={'event_id': event.id})
    response = client.post(url, post_data)

    # Render clearing_results.html
    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert "event_planner/clearing_results.html" in templates
    context = response.context
    expected_keys = [
        "event", "tasks", "total_actual", "total_budget", "share",
        "division_results", "selected_honorees", "selected_profiles",
        "selected_payers", "paid_by", "transactions", "total_net", "total_trans",
        "payer_dict_json", "honoree_ids_json"
    ]
    for key in expected_keys:
        assert key in context

# -------------------------------------------------------------
# EVENT CREATE: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_redirect_anonymous_get(client):
    url = reverse('create_event')
    response = client.get(url)
    assert response.status_code == 302
    assert 'login' in response.url.lower()

# -------------------------------------------------------------
# EVENT CREATE: POST request by an anonymous user 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_redirect_anonymous_post(client):
    url = reverse('create_event')
    response = client.post(url, {})
    assert response.status_code == 302
    assert 'login' in response.url.lower()

# -------------------------------------------------------------
# EVENT CREATE: GET request by a logged‑in user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_get_returns_form(client, create_user_with_scores):
    # Create a test user with minimal valid scores.
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    response = client.get(url)

    assert response.status_code == 200
    assert 'form' in response.context
    templates = [t.name for t in response.templates]
    assert 'event_planner/create_event.html' in templates

# -------------------------------------------------------------
# EVENT CREATE: valid POST creates an event and auto‑assigns the creator as a manager
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_post_valid_creates_event(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    valid_data = {
        'title': 'My Test Event',
        'date': '2025-04-04', 
        'event_type': 'birthday',
        'description': 'A description of the event'
    }
    event_count_before = Event.objects.count()
    participant_count_before = EventParticipant.objects.count()
    response = client.post(url, valid_data)

    # Redirect on success 
    assert response.status_code == 200, f"Form errors: {response.context.get('form').errors if 'form' in response.context else 'No form in context'}"
    assert Event.objects.count() == event_count_before + 1

    event = Event.objects.latest('id')
    # Creator is initial manager
    assert event.created_by == user
    manager_exists = EventParticipant.objects.filter(event=event, user_profile=user.userprofile, role='manager').exists()
    assert manager_exists
    # Verify redirect URL
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    content = response.content.decode('utf-8')
    assert f'window.top.location.href = "{expected_redirect}"' in content

# -------------------------------------------------------------
# EVENT CREATE: POST with missing title
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_post_invalid_title(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {
        'date': '2025-04-04',
        'event_type': 'birthday',
        'description': 'A description of the event'
    }
    event_count_before = Event.objects.count()
    response = client.post(url, invalid_data)

    # Ivalid form re-renders the template
    assert response.status_code == 200
    messages = list(get_messages(response.wsgi_request))
    error = any("Title" in m.message for m in messages)
    assert error
    # No new event should be created
    assert Event.objects.count() == event_count_before

# -------------------------------------------------------------
# EVENT CREATE: POST with missing event_type
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_post_invalid_event_type(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {
        'title': 'Event with no date',
        'description': 'A description of the event'
    }
    event_count_before = Event.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 200
    messages = list(get_messages(response.wsgi_request))
    errors = any("Event_type" in m.message for m in messages)
    assert errors
    assert Event.objects.count() == event_count_before

# -------------------------------------------------------------
# EVENT CREATE: POST with empty data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_post_empty_data(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {}
    event_count_before = Event.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 200
    messages = list(get_messages(response.wsgi_request))
    assert any("Title" in m.message for m in messages)
    assert any("Event_type" in m.message for m in messages)
    assert Event.objects.count() == event_count_before

# -------------------------------------------------------------
# EVENT CREATE: valid POST with all optional fields
# -------------------------------------------------------------
# Test that a valid POST with all optional fields creates an event with correct data.
@pytest.mark.django_db
def test_create_event_post_valid_with_all_fields(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    valid_data = {
        'title': 'Full Event',
        'date': '2025-04-04',
        'description': 'A description of the event',
        'event_type': 'birthday', 
        'time': '12:30:00',
        'location': 'Test Location'
    }
    response = client.post(url, valid_data)

    assert response.status_code == 200
    event = Event.objects.latest('id')
    assert event.title == 'Full Event'
    assert event.description == 'A description of the event'
    assert event.event_type == 'birthday'
    assert event.time.strftime('%H:%M:%S') == '12:30:00'
    assert event.location == 'Test Location'

# -------------------------------------------------------------
# EVENT CREATE: valid POST with success message
# -------------------------------------------------------------
def test_create_event_valid_success_message(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    valid_data = {
        'title': 'Full Event',
        'date': '2025-04-04',
        'description': 'A description of the event',
        'event_type': 'birthday', 
        'time': '12:30:00',
        'location': 'Test Location'
    }
    response = client.post(url, valid_data, follow=True)
    messages = list(get_messages(response.wsgi_request))
    
    success_messages = [m.message for m in messages if "Event created successfully" in m.message]
    assert success_messages

# -------------------------------------------------------------
# EVENT CREATE: invalid POST with error message
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_invalid_error_message(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {
        'description': 'No data'
    }
    response = client.post(url, invalid_data)
    messages = list(get_messages(response.wsgi_request))
    error_message = any("Please correct the errors below." in m.message for m in messages)
    assert error_message

# -------------------------------------------------------------
# EVENT CREATE: invalid form retains submitted data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_invalid_form_data_persistence(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {
        'title': '',  # invalid
        'date': '2025-04-04',
        'event_type': 'birthday', 
        'description': 'Persisted data test'
    }
    response = client.post(url, invalid_data)

    form = response.context.get('form')
    assert form is not None
    assert form.data.get('description') == 'Persisted data test'

# -------------------------------------------------------------
# EVENT CREATE: invalid form does not create EventParticipant
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_invalid_no_event_participant(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    invalid_data = {
        'title': '',  # invalid
        'date': '2025-04-04',
        'event_type': 'birthday', 
        'description': 'Invalid event'
    }
    event_count_before = Event.objects.count()
    participant_count_before = EventParticipant.objects.count()
    response = client.post(url, invalid_data)

    assert Event.objects.count() == event_count_before
    assert EventParticipant.objects.count() == participant_count_before

# -------------------------------------------------------------
# EVENT CREATE: redirection URL after successful POST
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_event_redirect_url(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_event')
    valid_data = {
        'title': 'Full Event',
        'date': '2025-04-04',
        'description': 'A description of the event',
        'event_type': 'birthday', 
        'time': '12:30:00',
        'location': 'Test Location'
    }
    response = client.post(url, valid_data)
    event = Event.objects.latest('id')

    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    content = response.content.decode('utf-8')
    assert f'window.top.location.href = "{expected_redirect}"' in content

# -------------------------------------------------------------
# EVENT EDIT: GET request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_redirects_anonymous_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    login_url = settings.LOGIN_URL
    assert login_url in response.url

# -------------------------------------------------------------
# EVENT EDIT: POST request by anonymous user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_redirects_anonymous_post(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    login_url = settings.LOGIN_URL
    assert login_url in response.url

# -------------------------------------------------------------
# EVENT EDIT: GET request by logged-in user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_get_returns_context(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event For Editing", description="Edit me")
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 200
    # Event instance is in the context
    assert 'event' in response.context
    # Form is pre-populated with event data
    form = response.context.get('form')
    assert form is not None
    assert form.instance.id == event.id
    # Additional forms are in the context
    for key in ['task_form', 'edit_task_form', 'role_form']:
        assert key in response.context
    # is_manager flag is True (the user is assigned manager)
    assert response.context.get('is_manager') is True

# -------------------------------------------------------------
# EVENT EDIT: GET request by logged-in user who is not manager
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_is_manager_false(client, create_user_with_scores, create_event):
    # Create two users: event creator=manager and user<>manager
    manager = create_user_with_scores("manager", 1, 0, 0, 0, 0, 0)
    other = create_user_with_scores("other", 1, 0, 0, 0, 0, 0)
    event = create_event(manager, title="Managed Event")
    client.force_login(other)
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    response = client.get(url)

    # is_manager False for non-manager
    assert response.context.get('is_manager') is False

# -------------------------------------------------------------
# EVENT EDIT: valid POST updates the event, sets updated_by, redirects back
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_post_valid_updates_event(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Original Event", description="Original description")
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    # Change title and description
    valid_data = {
        'title': 'Updated Event Title',
        'date': '2025-05-05',
        'description': 'Updated description',
        'event_type': 'birthday'
    }
    response = client.post(url, valid_data)

    # Redirect back to edit_event_detail
    assert response.status_code == 302
    updated_event = Event.objects.get(id=event.id)
    assert updated_event.title == 'Updated Event Title'
    assert updated_event.description == 'Updated description'
    # updated_by is set to logged-in user
    assert updated_event.updated_by == user
    # Redirect URL is correct
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT: invalid POST with error messages
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_post_invalid_shows_errors(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Original Event", description="Original description")
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    invalid_data = {
        'title': '',    # invalid
        'date': '2025-05-05',
        'description': 'Updated description',
        'event_type': 'birthday'
    }
    response = client.post(url, invalid_data)

    # View re-renders with form errors
    assert response.status_code == 200
    form = response.context.get('form')
    assert form is not None
    # Errors present on title field
    assert 'title' in form.errors
    messages = list(get_messages(response.wsgi_request))
    # Error mention missing title
    error = any("Title" in m.message for m in messages)
    assert error
    # Event is not updated
    unchanged_event = Event.objects.get(id=event.id)
    assert unchanged_event.title == "Original Event"

# -------------------------------------------------------------
# EVENT EDIT: requested event does not exist
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_nonexistent_event_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)

    # event_id does not exist
    non_existent_id = 9999
    url = reverse('edit_event_detail', kwargs={'event_id': non_existent_id})
    response = client.get(url)
    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT: form populated with data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_event_detail_form_initial_data(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    # Create event with values
    event = create_event(user, title="Original Event", description="Original description", event_type="other")
    url = reverse('edit_event_detail', kwargs={'event_id': event.id})
    response = client.get(url)

    form = response.context.get('form')
    # Check that data is displayed in form
    assert form.initial.get('title') == event.title
    assert form.initial.get('description') == event.description
    assert form.initial.get('event_type') == event.event_type

# -------------------------------------------------------------
# EVENT EDIT ADD ROLE: GET request (non-POST) redirects to edit_event_detail
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_role_get_redirects(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('add_role', kwargs={'event_id': event.id})
    response = client.get(url)

    # For non-POST methods, the view immediately redirects.
    assert response.status_code == 302
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT ADD ROLE: invalid POST with error message
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_role_post_invalid_data_shows_error(client, create_user_with_scores, create_event):
    user = create_user_with_scores("manager", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Invalid Data Event")
    url = reverse('add_role', kwargs={'event_id': event.id})
    # invalid data
    invalid_data = {
        'role': 'attendee'
    }
    participant_count_before = EventParticipant.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 302
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.url == expected_redirect
    # No eventParticipant created
    assert EventParticipant.objects.count() == participant_count_before
    # Error message
    messages = list(get_messages(response.wsgi_request))
    error_messages = [m.message for m in messages if "There was an error" in m.message]
    assert error_messages

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: GET request returns HttpResponseNotAllowed
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_get_not_allowed(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.get(url)

    # view only allows POST
    assert response.status_code == 405

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: POST with missing participant_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_missing_participant_id(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {}) 

    messages = list(get_messages(response.wsgi_request))
    errors = any("No participant specified" in m.message for m in messages)
    assert errors
    # Redirect to edit_event_detail
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: POST with a non-numeric participant_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_non_numeric_participant_id(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {'participant_id': 'abc'})

    messages = list(get_messages(response.wsgi_request))
    errors = any("Invalid participant ID" in m.message for m in messages)
    assert errors
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: POST with a non-existing participant_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_nonexistent_participant(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {'participant_id': '9999'})

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: delete last manager returns an error
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_only_manager_not_deleted(client, create_user_with_scores, create_event):
    user = create_user_with_scores("manager", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Only Manager Event")
    url = reverse('delete_role', kwargs={'event_id': event.id})
    participant = EventParticipant.objects.get(event=event, user_profile=user.userprofile, role='manager')
    print(participant.id)
    response = client.post(url, {'participant_id': participant.id})

    messages = list(get_messages(response.wsgi_request))
    errors = any("Cannot delete the only manager" in m.message for m in messages)
    assert errors
    # manager still exists
    assert EventParticipant.objects.filter(id=participant.id).exists()
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: delete one of multiple managers
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_manager_deleted_multiple_managers(client, create_user_with_scores, create_event):
    manager1 = create_user_with_scores("manager1", 1, 0, 0, 0, 0, 0)
    manager2 = create_user_with_scores("manager2", 1, 0, 0, 0, 0, 0)
    client.force_login(manager1)
    event = create_event(manager1, title="Multiple Manager Event")
    participant1 = EventParticipant.objects.get(event=event, user_profile=manager1.userprofile, role='manager')
    participant2 = EventParticipant.objects.create(event=event, user_profile=manager2.userprofile, role='manager')
    # Delete manager2
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {'participant_id': str(participant2.id)})

    messages = list(get_messages(response.wsgi_request))
    success_found = any("Participant deleted successfully" in m.message for m in messages)
    assert success_found
    assert not EventParticipant.objects.filter(id=participant2.id).exists()
    assert EventParticipant.objects.filter(id=participant1.id).exists()
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: delete a non-manager participant
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_non_manager_deleted(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Non-Manager Event")
    attendee = EventParticipant.objects.create(event=event, user_profile=user.userprofile, role='attendee')
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {'participant_id': str(attendee.id)})

    messages = list(get_messages(response.wsgi_request))
    success_found = any("Participant deleted successfully" in m.message for m in messages)
    assert success_found
    assert not EventParticipant.objects.filter(id=attendee.id).exists()
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT DELETE ROLE: delete a non-participant
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_role_participant_not_in_event_returns_404(client, create_user_with_scores, create_event):
    user1 = create_user_with_scores("user1", 1, 0, 0, 0, 0, 0)
    user2 = create_user_with_scores("user2", 1, 0, 0, 0, 0, 0)
    client.force_login(user1)
    event = create_event(user1, title="User1 Event")
    event2 = create_event(user2, title="User2 Event")
    participant = EventParticipant.objects.create(event=event2, user_profile=user2.userprofile, role='attendee')
    url = reverse('delete_role', kwargs={'event_id': event.id})
    response = client.post(url, {'participant_id': str(participant.id)})

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: anonymous GET
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_redirects_anonymous_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('add_task', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: anonymous POST
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_redirects_anonymous_post(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    url = reverse('add_task', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: GET request by logged-in user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_get_returns_context(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event for Task")
    url = reverse('add_task', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/add_task_modal.html' in templates
    assert 'form' in response.context
    assert 'event' in response.context

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: valid POST creates task
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_post_valid_creates_task(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event for Task")
    url = reverse('add_task', kwargs={'event_id': event.id})
    valid_data = {
        'title': 'New Task',
        'description': 'Task description',
        'base_points': 10,
        'penalty_points': 0, 
        'due_date': '2025-01-02',
        'status': 'pending',  
    }
    task_count_before = event.tasks.count() if hasattr(event, 'tasks') else 0
    response = client.post(url, valid_data)

    # Redirect (302) upon success
    assert response.status_code == 302, (
        f"Expected 302 redirect, got {response.status_code}. "
        f"Form errors: {response.context.get('form').errors if response.context and 'form' in response.context else 'None'}"
    )
    updated_event = Event.objects.get(id=event.id)
    new_task = updated_event.tasks.last()
    assert new_task is not None
    assert new_task.title == 'New Task'
    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.url == expected_redirect

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: invalid POST re-renders form with errors
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_post_invalid_errors(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event for Task")
    url = reverse('add_task', kwargs={'event_id': event.id})
    invalid_data = {
        'title': '',
        'description': 'Task description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, invalid_data)

    assert response.status_code == 200
    form = response.context.get('form')
    assert form is not None
    assert 'title' in form.errors
    messages = list(get_messages(response.wsgi_request))
    errors = any("Title" in m.message for m in messages)
    assert errors

# -------------------------------------------------------------
# EVENT EDIT ADD TASK: GET request with non-existent event
# -------------------------------------------------------------
@pytest.mark.django_db
def test_add_task_nonexistent_event_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse('add_task', kwargs={'event_id': non_existent_id})
    response = client.get(url)

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: anonymous GET
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_redirects_anonymous_get(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    task = create_task(event)
    url = reverse('edit_task', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: anonymous POST
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_redirects_anonymous_post(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    task = create_task(event)
    url = reverse('edit_task', kwargs={'event_id': event.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: GET request by logged‑in user
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_get_logged_in_returns_redirect(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event)
    url = reverse('edit_task', kwargs={'event_id': event.id})
    response = client.get(url)

    expected = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: valid non-AJAX POST updates a task
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_post_valid_non_ajax(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Original Task", description="Original description")
    url = reverse('edit_task', kwargs={'event_id': event.id})
    valid_data = {
        'task_id': str(task.id),
        'title': 'Updated Task',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0, 
        'due_date': '2025-01-02',
        'status': 'pending', 
    }
    response = client.post(url, valid_data)

    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.title == 'Updated Task'
    assert updated_task.description == 'Updated description'

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: valid Ajax POST updates task
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_post_valid_ajax(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Original Task", description="Original description")
    url = reverse('edit_task', kwargs={'event_id': event.id})
    valid_data = {
        'task_id': str(task.id),
        'title': 'Updated Task',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0, 
        'due_date': '2025-01-02',
        'status': 'pending', 
    }
    response = client.post(url, valid_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data.get('success') is True
    updated_task = Task.objects.get(id=task.id)
    assert updated_task.title == 'Updated Task'
    assert updated_task.description == 'Updated description'

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: invalid POST re-renders with errors
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_post_invalid_shows_errors(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Original Task", description="Original description")
    url = reverse('edit_task', kwargs={'event_id': event.id})
    invalid_data = {
        'task_id': str(task.id),
        'title': '',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, invalid_data)

    assert response.status_code == 200
    form = response.context.get('edit_task_form')
    assert form is not None
    assert 'title' in form.errors
    messages = list(get_messages(response.wsgi_request))
    assert any("Title" in m.message for m in messages)
    assert response.context.get('open_edit_task_modal') is True
    templates = [t.name for t in response.templates]
    assert 'event_planner/edit_event_detail.html' in templates

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: POST with a missing task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_missing_task_id_returns_404(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('edit_task', kwargs={'event_id': event.id})
    invalid_data = {
        'title': 'Updated Task',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, invalid_data)

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: POST with invalid task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_task_not_in_event_returns_404(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event1 = create_event(user, title="Event 1")
    event2 = create_event(user, title="Event 2")
    task = create_task(event2, title="Task in Event2")
    url = reverse('edit_task', kwargs={'event_id': event1.id})
    data = {
        'task_id': str(task.id),
        'title': 'Updated Title',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, data)

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: assigned_to queryset is properly restricted
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_assigned_to_queryset_restriction(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    allowed_user = create_user_with_scores("allowed", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Event with allowed")
    EventParticipant.objects.create(event=event, user_profile=allowed_user.userprofile, role='manager')
    task = create_task(event, title="Task for assigned_to test")
    url = reverse('edit_task', kwargs={'event_id': event.id})
    data = {
       'task_id': str(task.id),
       'title': '',
       'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, data)

    assert response.status_code == 200
    form = response.context.get('edit_task_form')
    assert form is not None
    # queryset for 'assigned_to' limited to allowed profiles
    allowed_ids = list(
        event.eventparticipant_set.filter(role__in=['manager', 'organizer', 'honouree'])
        .values_list('user_profile__id', flat=True)
    )
    qs_ids = list(form.fields['assigned_to'].queryset.values_list('id', flat=True))
    for uid in qs_ids:
        assert uid in allowed_ids

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: GET request redirects to edit_event_detail
# -------------------------------------------------------------
# Test that a GET request to edit_task (by logged‑in user) redirects to edit_event_detail.
@pytest.mark.django_db
def test_edit_task_get_redirects_to_edit_event_detail(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('edit_task', kwargs={'event_id': event.id})
    response = client.get(url)

    expected = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected

# -------------------------------------------------------------
# EVENT EDIT EDIT TASK: GET request populates form with current data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_form_initial_data(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event, title="Original Task", description="Original description")
    url = reverse('edit_task', kwargs={'event_id': event.id})
    invalid_data = {
        'task_id': str(task.id),
        'title': '',
        'description': 'Updated description',
        'base_points': 10,
        'penalty_points': 0,
    }
    response = client.post(url, invalid_data)
    form = response.context.get('edit_task_form')
    assert form.data.get('description') == 'Updated description'
    assert 'title' in form.errors

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: anonymous POST
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_redirects_anonymous_post(client, create_event, create_task, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    event = create_event(user)
    task = create_task(event)
    url = reverse('delete_task', kwargs={'event_id': event.id})
    response = client.post(url, {'task_id': str(task.id)})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: GET request returns HttpResponseNotAllowed
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_method_not_allowed_get(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_task', kwargs={'event_id': event.id})
    response = client.get(url)

    assert response.status_code == 405

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: POST with missing task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_post_missing_task_id(client, create_user_with_scores, create_event):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    url = reverse('delete_task', kwargs={'event_id': event.id})
    response = client.post(url, {'task_id': ''})

    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect
    messages = list(get_messages(response.wsgi_request))
    errors = any("No task specified for deletion" in m.message for m in messages)
    assert errors

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: POST with invalid event_id 
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_invalid_event_id_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event_id = 9999
    url = reverse('delete_task', kwargs={'event_id': event_id})
    response = client.post(url, {'task_id': '1'})

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: POST with non-existent task_id
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_invalid_task_for_event_returns_404(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event1 = create_event(user, title="Event 1")
    event2 = create_event(user, title="Event 2")
    task = create_task(event1)
    url = reverse('delete_task', kwargs={'event_id': event2.id})
    response = client.post(url, {'task_id': str(task.id)})

    assert response.status_code == 404

# -------------------------------------------------------------
# EVENT EDIT DELETE TASK: valid POST deletes the task
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_post_valid_deletes_task(client, create_user_with_scores, create_event, create_task):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user)
    task = create_task(event)
    task_id = task.id

    assert task is not None
    url = reverse('delete_task', kwargs={'event_id': event.id})
    response = client.post(url, {'task_id': str(task_id)})

    expected_redirect = reverse('edit_event_detail', kwargs={'event_id': event.id})
    assert response.status_code == 302
    assert response.url == expected_redirect

    with pytest.raises(Task.DoesNotExist):
        task.refresh_from_db()
    messages = list(get_messages(response.wsgi_request))
    success_found = any("Task deleted successfully" in m.message for m in messages)
    assert success_found



# -------------------------------------------------------------
# TASK TEMPLATE views
# -------------------------------------------------------------
# -------------------------------------------------------------
# TASK TEMPLATE LIST: anonymous GET redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_redirects_anonymous_get(client):
    url = reverse('task_template_list')
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE LIST: anonymous POST redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_redirects_anonymous_post(client):
    url = reverse('task_template_list')
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE LIST: valid GET request
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_get_returns_correct_template(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('task_template_list')
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/task_template_list.html' in templates

# -------------------------------------------------------------
# TASK TEMPLATE LIST: empty context when no templates exist
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_context_empty_when_no_templates(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('task_template_list')
    response = client.get(url)

    context = response.context
    assert 'event_templates' in context
    assert 'gift_templates' in context
    assert list(context['event_templates']) == []
    assert list(context['gift_templates']) == []

# -------------------------------------------------------------
# TASK TEMPLATE LIST: template type filtered correctly
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_filters_templates(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event_template1 = create_task_template("Event Template 1", task_type='event')
    event_template2 = create_task_template("Event Template 2", task_type='event')
    gift_template1 = create_task_template("Gift Template 1", task_type='gift')
    gift_template2 = create_task_template("Gift Template 2", task_type='gift')
    other_template = create_task_template("Other Template", task_type='other')
    url = reverse('task_template_list')
    response = client.get(url)

    context = response.context
    event_templates = list(context['event_templates'])
    gift_templates = list(context['gift_templates'])
    # only event templates are returned
    assert event_template1 in event_templates
    assert event_template2 in event_templates
    assert other_template not in event_templates
    # only gift templates are returned
    assert gift_template1 in gift_templates
    assert gift_template2 in gift_templates
    assert other_template not in gift_templates

# -------------------------------------------------------------
# TASK TEMPLATE LIST: context keys event_templates and gift_templates exist
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_context_keys_exist(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('task_template_list')
    response = client.get(url)

    context = response.context
    for key in ['event_templates', 'gift_templates']:
        assert key in context

# -------------------------------------------------------------
# TASK TEMPLATE LIST: correct count for multiple templates
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_multiple_templates_counts(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    create_task_template("Event Template 1", task_type='event')
    create_task_template("Event Template 2", task_type='event')
    create_task_template("Event Template 3", task_type='event')
    create_task_template("Gift Template 1", task_type='gift')
    create_task_template("Gift Template 2", task_type='gift')
    url = reverse('task_template_list')
    response = client.get(url)

    context = response.context
    assert context['event_templates'].count() == 3
    assert context['gift_templates'].count() == 2

# -------------------------------------------------------------
# TASK TEMPLATE LIST: behavior with unexpected task_type values
# -------------------------------------------------------------
@pytest.mark.django_db
def test_task_template_list_excludes_unexpected_task_types(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    valid_event = create_task_template("Valid Event", task_type='event')
    valid_gift = create_task_template("Valid Gift", task_type='gift')
    invalid_template = create_task_template("Invalid", task_type='other')
    url = reverse('task_template_list')
    response = client.get(url)

    context = response.context
    event_templates = list(context['event_templates'])
    gift_templates = list(context['gift_templates'])
    assert valid_event in event_templates
    assert valid_gift in gift_templates
    assert invalid_template not in event_templates
    assert invalid_template not in gift_templates

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: anonymous GET redirects to login
# -------------------------------------------------------------
# Test that an anonymous GET request to create_task_template is redirected to login.
@pytest.mark.django_db
def test_create_task_template_redirects_anonymous_get(client):
    url = reverse('create_task_template')
    response = client.get(url)

    assert response.status_code == 302
    assert 'login' in response.url.lower()

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: anonymous POST redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_redirects_anonymous_post(client):
    url = reverse('create_task_template')
    response = client.post(url, {})

    assert response.status_code == 302
    assert 'login' in response.url.lower()

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: GET request returns correct template and context
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_get_returns_form(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/create_task_template.html' in templates
    assert 'form' in response.context

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: valid POST creates TaskTemplate
# -------------------------------------------------------------
# Test that a valid POST creates a TaskTemplate and returns success JSON.
@pytest.mark.django_db
def test_create_task_template_post_valid(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    valid_data = {
        'title': 'Test Template',
        'description': 'A description for the template',
        'base_points': 10,
        'penalty_points': 0,
        'task_type': 'event'
    }
    template_count_before = TaskTemplate.objects.count()
    response = client.post(url, valid_data)

    # 200 status code with JSON success
    assert response.status_code == 200
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is True
    assert TaskTemplate.objects.count() == template_count_before + 1

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: invalid POST with missing fields
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_post_missing_title(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    invalid_data = {
        'description': 'Template without title',
        'base_points': 10,
        'penalty_points': 0,
        'task_type': 'event'
    }
    template_count_before = TaskTemplate.objects.count()
    response = client.post(url, invalid_data)

    # 400 status code, JSON with False, errors
    assert response.status_code == 400
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is False
    assert 'title' in data.get('errors', {})
    assert TaskTemplate.objects.count() == template_count_before

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: POST with invalid penalty_points
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_post_invalid_penalty_points(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    invalid_data = {
        'title': 'Invalid Penalty Template',
        'description': 'Penalty points must be <= 0',
        'base_points': 10,
        'penalty_points': 5,
        'task_type': 'event'
    }
    template_count_before = TaskTemplate.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 400
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is False
    assert 'penalty_points' in data.get('errors', {})
    assert TaskTemplate.objects.count() == template_count_before

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: POST with non-numeric base_points
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_post_non_numeric_base_points(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    invalid_data = {
        'title': 'Non-numeric Base Points',
        'description': 'Base points should be numeric',
        'base_points': 'ten', 
        'penalty_points': 0,
        'task_type': 'event'
    }
    template_count_before = TaskTemplate.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 400
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is False
    assert 'base_points' in data.get('errors', {})
    assert TaskTemplate.objects.count() == template_count_before

# -------------------------------------------------------------
# TASK TEMPLATE CREATE: POST with multiple invalid fields
# -------------------------------------------------------------
@pytest.mark.django_db
def test_create_task_template_post_multiple_invalid_fields(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('create_task_template')
    invalid_data = {
        'title': '',
        'description': 'Multiple errors',
        'base_points': 'invalid',  
        'penalty_points': 5,
        'task_type': 'event'
    }
    template_count_before = TaskTemplate.objects.count()
    response = client.post(url, invalid_data)

    assert response.status_code == 400
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is False
    errors = data.get('errors', {})
    # errors for title, base_points, penalty_points
    assert 'title' in errors
    assert 'base_points' in errors
    assert 'penalty_points' in errors
    assert TaskTemplate.objects.count() == template_count_before

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: anonymous GET redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_redirects_anonymous_get(client, create_task_template):
    template = create_task_template()
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: anonymous POST redirects to login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_redirects_anonymous_post(client, create_task_template):
    template = create_task_template()
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: GET request returns edit form and template data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_get_returns_context(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="Test Template", description="Prepopulated description")
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/edit_task_template.html' in templates
    assert 'form' in response.context
    assert 'template' in response.context
    form = response.context['form']
    # form is prepopulated with the TaskTemplate data
    assert form.initial.get('title') == template.title
    assert form.initial.get('description') == template.description
    assert form.initial.get('task_type') == template.task_type

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: valid POST updates task template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_post_valid_updates_template(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="Old Title", description="Old description", base_points=10, penalty_points=0, task_type="event")
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    valid_data = {
        'title': 'Updated Template Title',
        'description': 'Updated description',
        'base_points': 15,
        'penalty_points': 0,
        'task_type': 'event'
    }
    response = client.post(url, valid_data)

    assert response.status_code == 200
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is True
    template.refresh_from_db()
    assert template.title == 'Updated Template Title'
    assert template.description == 'Updated description'
    assert template.base_points == 15

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: invalid POST returns JSON with False and errors
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_post_invalid_returns_json_errors(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="Valid Title", description="Valid description", base_points=10, penalty_points=0, task_type="event")
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    invalid_data = {
        'title': '',
        'description': 'New description',
        'base_points': 10,
        'penalty_points': 0,
        'task_type': 'event'
    }
    response = client.post(url, invalid_data)

    assert response.status_code == 400
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is False
    assert 'title' in data.get('errors', {})

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: GET request for non-existent task template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_nonexistent_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse('edit_task_template', kwargs={'template_id': non_existent_id})
    response = client.get(url)

    assert response.status_code == 404

# -------------------------------------------------------------
# TASK TEMPLATE EDIT: valid POST returns JSON content with proper keys
# -------------------------------------------------------------
@pytest.mark.django_db
def test_edit_task_template_post_json_structure(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="Json Test Template", description="Desc", base_points=10, penalty_points=0, task_type="event")
    url = reverse('edit_task_template', kwargs={'template_id': template.id})
    valid_data = {
        'title': 'Json Updated Template',
        'description': 'Json updated description',
        'base_points': 20,
        'penalty_points': 0,
        'task_type': 'event'
    }
    response = client.post(url, valid_data)

    assert response.status_code == 200
    data = json.loads(response.content.decode('utf-8'))
    assert 'success' in data
    assert data['success'] is True

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: anonymous GET redirects to the login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_template_redirects_anonymous_get(client, create_task_template):
    template = create_task_template()
    url = reverse('delete_task_template', kwargs={'template_id': template.id})
    response = client.get(url)

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: anonymous POST redirects to the login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_template_redirects_anonymous_post(client, create_task_template):
    template = create_task_template()
    url = reverse('delete_task_template', kwargs={'template_id': template.id})
    response = client.post(url, {})

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: GET returns confirmation page
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_template_get_returns_confirmation_page(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="Confirm Delete", description="Confirm delete test")
    url = reverse('delete_task_template', kwargs={'template_id': template.id})
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/delete_task_template_confirm.html' in templates
    assert response.context.get('template').id == template.id

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: GET does not delete task template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_template_get_does_not_delete_template(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="No Delete on GET")
    url = reverse('delete_task_template', kwargs={'template_id': template.id})
    response = client.get(url)

    assert response.status_code == 200
    assert TaskTemplate.objects.filter(id=template.id).exists()

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: valid POST deletes task template
# -------------------------------------------------------------
@pytest.mark.django_db
def test_delete_task_template_post_deletes_template(client, create_user_with_scores, create_task_template):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    template = create_task_template(title="To Be Deleted")
    url = reverse('delete_task_template', kwargs={'template_id': template.id})
    response = client.post(url, {})

    assert response.status_code == 200
    data = json.loads(response.content.decode('utf-8'))
    assert data.get('success') is True
    assert not TaskTemplate.objects.filter(id=template.id).exists()

# -------------------------------------------------------------
# TASK TEMPLATE DELETE: invalid POST with non-existent template
# -------------------------------------------------------------
# Test that a POST request with a non-existent template id returns a 404 status.
@pytest.mark.django_db
def test_delete_task_template_nonexistent_returns_404(client, create_user_with_scores):
    user = create_user_with_scores("testuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    non_existent_id = 9999
    url = reverse('delete_task_template', kwargs={'template_id': non_existent_id})
    response = client.get(url)

    assert response.status_code == 404
    response_post = client.post(url, {})
    assert response_post.status_code == 404




# -------------------------------------------------------------
# CALENDAR views
# -------------------------------------------------------------
# -------------------------------------------------------------
# CALENDAR: anonymous GET redirects to the login
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_redirects_anonymous(client):
    url = reverse('calendar_view')
    response = client.get(url)

    assert response.status_code == 302
    login_url = settings.LOGIN_URL
    assert login_url in response.url

# -------------------------------------------------------------
# CALENDAR: GET returns calendar template and context
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_returns_template_and_context(client, create_user_with_scores):
    user = create_user_with_scores("caluser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('calendar_view')
    response = client.get(url)

    assert response.status_code == 200
    templates = [t.name for t in response.templates]
    assert 'event_planner/calendar.html' in templates
    assert 'calendar_events_json' in response.context
    events = json.loads(response.context['calendar_events_json'])
    assert isinstance(events, list)

# -------------------------------------------------------------
# CALENDAR: birthday appears in calendar
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_includes_birthday_event(client, create_user_with_scores):
    user = create_user_with_scores("birthdayuser", 1, 0, 0, 0, 0, 0)
    bday = date(1990, 6, 15)
    user.userprofile.birthday = bday
    user.userprofile.save()
    client.force_login(user)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    birthday_events = [e for e in events if e.get('extendedProps', {}).get('type') == 'birthday']
    assert len(birthday_events) >= 1
    assert any(user.username in e['title'] for e in birthday_events)

# -------------------------------------------------------------
# CALENDAR: event with date, time, location appears in calendar
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_includes_event(client, create_user_with_scores):
    user = create_user_with_scores("eventuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    # Create an event with time and location set.
    event = Event.objects.create(
        title="Calendar Test Event",
        date="2025-05-05",
        time="10:00:00",
        location="Test Location",
        description="Test event",
        event_type="birthday",
        created_by=user
    )
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    event_events = [e for e in events if e.get('title') == "Calendar Test Event"]
    assert len(event_events) == 1
    assert event_events[0].get('extendedProps', {}).get('type') == 'event'
    assert event_events[0].get('color') == 'ForestGreen'

# -------------------------------------------------------------
# CALENDAR: task with future due date appears not overdue
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_includes_task_not_overdue(client, create_user_with_scores, create_event):
    user = create_user_with_scores("taskuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Task Event")
    future_due_date = timezone.now() + timedelta(days=2)
    task = Task.objects.create(
        event=event,
        title="Future Task",
        description="Not overdue task",
        base_points=10,
        penalty_points=0,
        status="pending",
        due_date=future_due_date
    )
    task.assigned_to.add(user.userprofile)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    task_events = [e for e in events if e.get('extendedProps', {}).get('type') == 'task' and "Future Task" in e.get('title', "")]
    assert len(task_events) >= 1
    for te in task_events:
        assert " (Overdue)" not in te['title']
        assert te.get('extendedProps', {}).get('icon') == 'bi bi-briefcase'

# -------------------------------------------------------------
# CALENDAR: overdue task appears with overdue indication
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_includes_task_overdue(client, create_user_with_scores, create_event):
    user = create_user_with_scores("overduetaskuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    event = create_event(user, title="Overdue Task Event")
    past_due_date = timezone.now() - timedelta(days=2)
    task = Task.objects.create(
        event=event,
        title="Overdue Task",
        description="Task is overdue",
        base_points=10,
        penalty_points=0,
        status="pending",
        due_date=past_due_date
    )
    task.assigned_to.add(user.userprofile)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    overdue_task_events = [e for e in events if e.get('extendedProps', {}).get('type') == 'task' and "Overdue Task" in e.get('title', "")]
    assert len(overdue_task_events) >= 1
    for te in overdue_task_events:
        assert " (Overdue)" in te['title']
        assert te.get('extendedProps', {}).get('icon') == 'bi bi-exclamation-triangle'
    extra_overdue_events = [e for e in events if e.get('title') == 'overdue' and e.get('color') == 'Red']
    assert len(extra_overdue_events) >= 1

# -------------------------------------------------------------
# CALENDAR: gift search appears when user is not donee
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_includes_gift_search(client, create_user_with_scores, create_gift_search):
    user = create_user_with_scores("giftuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    other = create_user_with_scores("othergift", 1, 0, 0, 0, 0, 0)
    deadline = timezone.now() + timedelta(days=5)
    gs = create_gift_search(user, "Holiday Gift", deadline, other.userprofile)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    gift_events = [e for e in events if e.get('extendedProps', {}).get('type') == 'gift' and "Holiday Gift" in e.get('title', "")]
    assert len(gift_events) >= 1

# -------------------------------------------------------------
# CALENDAR: gift search is not displayed for donee
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_excludes_gift_search_for_donee(client, create_user_with_scores, create_gift_search):
    user = create_user_with_scores("giftuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    deadline = timezone.now() + timedelta(days=5)
    gs = create_gift_search(user, "Self Gift", deadline, user.userprofile)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    gift_events = [e for e in events if e.get('extendedProps', {}).get('type') == 'gift' and "Self Gift" in e.get('title', "")]
    assert len(gift_events) == 0

# -------------------------------------------------------------
# CALENDAR: JSON structure is valid
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_json_structure(client, create_user_with_scores):
    user = create_user_with_scores("jsonuser", 1, 0, 0, 0, 0, 0)
    client.force_login(user)
    url = reverse('calendar_view')
    response = client.get(url)

    json_str = response.context.get('calendar_events_json')
    data = json.loads(json_str)
    assert isinstance(data, list)
    for item in data:
        assert 'title' in item
        assert 'start' in item
        assert 'color' in item
        assert 'textColor' in item
        if 'extendedProps' in item:
            assert isinstance(item['extendedProps'], dict)

# -------------------------------------------------------------
# CALENDAR: calendar_events_json is empty without data
# -------------------------------------------------------------
@pytest.mark.django_db
def test_calendar_view_no_events(client, create_user_with_scores):
    # User without birthday
    user = create_user_with_scores("emptyuser", 1, 0, 0, 0, 0, 0)
    user.userprofile.birthday = None
    user.userprofile.save()
    client.force_login(user)
    url = reverse('calendar_view')
    response = client.get(url)

    events = json.loads(response.context['calendar_events_json'])
    # Assuming this test runs in isolation, no other users exist.
    assert events == []



# -------------------------------------------------------------
# CALENDAR: 
# -------------------------------------------------------------




# -------------------------------------------------------------
# CALENDAR: 
# -------------------------------------------------------------
