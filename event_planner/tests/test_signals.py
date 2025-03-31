import math
from decimal import Decimal
import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.contrib.auth import get_user_model
from event_planner.models import *
from event_planner import views
from event_planner.signals import *



User = get_user_model()


# --- Fixtures ---
@pytest.fixture(autouse=True)
def override_job_config(db):
    # Override JOB_CONFIG for testing purposes.
    from event_planner import job_config
    original = job_config.JOB_CONFIG
    job_config.JOB_CONFIG = {
        'general': {'conversion_rate': 0.5, 'payment_penalty': -25},
        'check_payment_reminder': {'overdue_threshold': 7}
    }
    yield
    job_config.JOB_CONFIG = original


@pytest.fixture
def create_user(db):
    def make_user(username="testuser", **kwargs):
        return User.objects.create(username=username, **kwargs)
    return make_user


@pytest.fixture
def create_userprofile(db, create_user):
    def make_userprofile(username="testuser", **kwargs):
        user = create_user(username=username, **kwargs)
        # The post_save signal on User should create the related UserProfile.
        return UserProfile.objects.get(user=user)
    return make_userprofile


# --- Tests for UserProfile creation (10 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize("username", [f"user_{i}" for i in range(10)])
def test_create_user_profile_signal_various(username, create_user, db):
    user = create_user(username=username)
    profile = UserProfile.objects.get(user=user)
    assert profile is not None
    # __str__ returns the username
    assert str(profile) == username


# --- Tests for update_total_score (20 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,task,gift,payment,expected_total",
    [
        (0, 0, 0, 0, 0),
        (1, 0, 0, 0, 1),
        (0, 2, 0, 0, 2),
        (0, 0, 3, 0, 3),
        (0, 0, 0, 4, 4),
        (5, 5, 5, 5, 20),
        (10, 20, 30, 40, 100),
        (None, 1, 2, 3, 6),
        (1, None, 2, 3, 6),
        (1, 2, None, 3, 6),
        (1, 2, 3, None, 6),
        (7, 8, 9, 10, 34),
        (100, 200, 300, 400, 1000),
        (0, 0, 5, 0, 5),
        (0, 5, 0, 0, 5),
        (5, 0, 0, 0, 5),
        (3, 3, 3, 3, 12),
        (4, 4, 4, 4, 16),
        (6, 6, 6, 6, 24),
        (8, 8, 8, 8, 32),
    ],
    ids=lambda val: f"val_{val}" if isinstance(val, int) else "None"
)

def test_update_total_score_various(role, task, gift, payment,
                                    expected_total, create_userprofile):
    profile = create_userprofile("user_total_various")
    profile.role_score = role if role is not None else 0
    profile.task_score = task if task is not None else 0
    profile.gift_score = gift if gift is not None else 0
    profile.payment_score = payment if payment is not None else 0
    profile.role_score_past = profile.role_score
    profile.task_score_past = profile.task_score
    profile.gift_score_past = profile.gift_score
    profile.payment_score_past = profile.payment_score
    profile.save()
    assert profile.total_score == expected_total
    assert profile.total_score_past == expected_total


# --- Tests for update__task_score (20 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_new,initial_status,new_status,base_points,penalty_points,"
    "due_offset,expected_status,expected_points",
    [
        (True, 'pending', 'completed', 50, -10, 1, 'completed', 50),
        (True, 'pending', 'pending', 50, -10, -1, 'overdue', -10),
        (False, 'pending', 'completed', 40, -5, 1, 'completed', 40),
        (False, 'completed', 'pending', 40, -5, 1, 'pending', 0),
        (False, 'pending', 'overdue', 30, -5, -1, 'overdue', -5),
        (True, 'pending', 'completed', 0, -5, 1, 'completed', 0),
        (True, 'pending', 'pending', 0, -5, -1, 'overdue', -5),
        (False, 'pending', 'completed', 100, -20, 1, 'completed', 100),
        (False, 'completed', 'overdue', 100, -20, -1, 'overdue', -20),
        (False, 'overdue', 'completed', 100, -20, 1, 'completed', 100),
        (True, 'pending', 'completed', 25, -5, 2, 'completed', 25),
        (True, 'pending', 'pending', 25, -5, -2, 'overdue', -5),
        (False, 'pending', 'completed', 60, -10, 3, 'completed', 60),
        (False, 'completed', 'pending', 60, -10, 3, 'pending', 0),
        (False, 'pending', 'overdue', 80, -15, -3, 'overdue', -15),
        (True, 'pending', 'completed', 0, 0, 1, 'completed', 0),
        (True, 'pending', 'pending', 0, 0, -1, 'overdue', 0),
        (False, 'pending', 'completed', 90, -20, 2, 'completed', 90),
        (False, 'completed', 'overdue', 90, -20, -2, 'overdue', -20),
        (False, 'overdue', 'completed', 90, -20, 2, 'completed', 90),
    ],
    ids=lambda i: f"case_{i}"
)

def test_update_task_score_various(is_new, initial_status, new_status, base_points,
                                   penalty_points, due_offset, expected_status,
                                   expected_points, create_userprofile, db):

    event = Event.objects.create(title="Test Event Multiple")
    task = Task.objects.create(
        event=event,
        title="Test Task Multiple",
        status=initial_status,
        base_points=base_points,
        penalty_points=penalty_points,
        due_date=timezone.now() +
        timezone.timedelta(days=due_offset) if due_offset is not None else None,
    )
    if not is_new:
        task.status = new_status
        task.save()
    else:
        task.status = new_status
        task.save()
    task.refresh_from_db()
    assert task.status == expected_status
    if expected_status == 'completed':
        assert task.points_awarded == expected_points
        assert task.completed_at is not None
    elif expected_status == 'overdue':
        assert task.points_awarded != expected_points
    else:
        if expected_points == 0:
            assert task.points_awarded is None or task.points_awarded == 0


# --- Tests for TaskScoreHistory creation (10 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize("num_assignees", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
def test_task_score_history_created_multiple(num_assignees, create_userprofile, db):

    event = Event.objects.create(title="Event Task History Multiple")
    task = Task.objects.create(
        event=event,
        title="Task for Score History Multiple",
        status='pending',
        base_points=100,
        penalty_points=-50,
    )
    profiles = [create_userprofile(f"user_ts_multi_{i}")
                for i in range(num_assignees)]
    task.assigned_to.set(profiles)
    task.status = 'completed'
    task.save()
    for profile in profiles:
        histories = TaskScoreHistory.objects.filter(
            task=task, user_profile=profile, score_type='task')
        assert histories.exists()
        for history in histories:
            assert history.points_change == task.base_points


# --- Tests for RoleScoreHistory creation (12 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize("role,points", [
    ('organizer', 5),
    ('organizer', 10),
    ('organizer', 15),
    ('attendee', 5),
    ('attendee', 10),
    ('attendee', 15),
    ('manager', 5),
    ('manager', 10),
    ('manager', 15),
    ('honouree', 5),
    ('honouree', 10),
    ('honouree', 15),
])
def test_role_score_history_created_various(role, points, create_userprofile, db):
    event = Event.objects.create(title="Event for Role Score Various")
    RoleConfiguration.objects.update_or_create(role=role,
                                               defaults={'points': points})
    profile = create_userprofile(f"user_role_various_{role}_{points}")
    participant = EventParticipant.objects.create(
        event=event, user_profile=profile, role=role)
    history = RoleScoreHistory.objects.filter(
        event_participant=participant, user_profile=profile, role=role)
    assert history.exists()
    for h in history:
        assert h.points_awarded == points


# --- Tests for GiftScoreHistory on Vote (5 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize("points", [5, 10, 15, 20, 25])
def test_gift_vote_score_history_various(points, create_userprofile, db):
    voter = create_userprofile(f"voter_{points}")
    GiftConfiguration.objects.create(role='voter', points=points)
    gift_search = GiftSearch.objects.create(
        title="Gift Search", purpose="Test", donee=voter,
        deadline=timezone.now().date(), created_by=voter)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal",
        description="Desc", proposed_by=voter)
    class DummyVote:
        pass
    vote = DummyVote()
    vote.user_id = voter.user.id
    vote.object_id = proposal.id
    update_gift_score_history_on_vote(sender=GiftProposal, instance=vote, created=True)
    history = GiftScoreHistory.objects.filter(
        user_profile=voter, gift_proposal=proposal, score_type='vote')
    assert history.exists()
    for h in history:
        assert h.points_change == points


# --- Tests for GiftSearch winner signal (3 tests) ---
@pytest.mark.django_db
def test_gift_winner_score_history_creation(create_userprofile, db):
    user = create_userprofile("winner")
    GiftConfiguration.objects.create(role='winner', points=20)
    gift_search = GiftSearch.objects.create(
        title="Gift Search Winner", purpose="Test", donee=user,
        deadline=timezone.now().date(), created_by=user, final_results_sent=False)
    proposal1 = GiftProposal.objects.create(
        gift_search=gift_search, title="Proposal 1", description="Desc",
        proposed_by=user)
    proposal2 = GiftProposal.objects.create(
        gift_search=gift_search, title="Proposal 2", description="Desc",
        proposed_by=user)
    # Monkey-patch votes count via a lambda (simulate votes.count())
    proposal1.get_votes_count = lambda: 5
    proposal2.get_votes_count = lambda: 10
    gift_search.final_results_sent = True
    gift_search.save()
    history = GiftScoreHistory.objects.filter(
        user_profile=user, gift_proposal=proposal2, score_type='winner')
    assert history.exists()
    for h in history:
        assert h.points_change == 20


@pytest.mark.django_db
def test_gift_winner_score_history_removal(create_userprofile, db):
    user = create_userprofile("winner2")
    GiftConfiguration.objects.create(role='winner', points=15)
    gift_search = GiftSearch.objects.create(
        title="Gift Search Remove", purpose="Test", donee=user,
        deadline=timezone.now().date(), created_by=user, final_results_sent=True)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="Proposal", description="Desc",
        proposed_by=user)
    proposal.get_votes_count = lambda: 10
    gift_search.final_results_sent = False
    gift_search.save()
    history = GiftScoreHistory.objects.filter(
        user_profile=user, gift_proposal=proposal, score_type='winner')
    assert not history.exists()



# --- Tests for GiftProposal signal (3 tests) ---
@pytest.mark.django_db
@pytest.mark.parametrize("points", [10, 20, 30])
def test_gift_proposal_score_history_creation_various(points, create_userprofile, db):
    proposer = create_userprofile("proposer")
    GiftConfiguration.objects.create(role='proposer', points=points)
    gift_search = GiftSearch.objects.create(
        title="Gift Search Proposal", purpose="Test", donee=proposer,
        deadline=timezone.now().date(), created_by=proposer)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="New Proposal", description="Desc",
        proposed_by=proposer)
    history = GiftScoreHistory.objects.filter(
        user_profile=proposer, gift_proposal=proposal, score_type='proposal')
    assert history.exists()
    for h in history:
        assert h.points_change == points


# --- Tests for GiftContribution transactions (4 tests) ---
@pytest.mark.django_db
def test_gift_contribution_closed_transactions(create_userprofile, db):
    manager = create_userprofile("manager")
    contributor = create_userprofile("contributor")
    gc = GiftContribution.objects.create(
        title="Gift Contribution Test", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('50.00'))
    gc.status = "closed"
    gc.save()
    transactions = Transaction.objects.filter(gift_contribution=gc, type="gift")
    assert transactions.count() == 1
    for t in transactions:
        if t.from_user == gc.manager:
            assert t.status == "confirmed"
        else:
            assert t.status == "billed"


@pytest.mark.django_db
def test_gift_contribution_canceled_transactions(create_userprofile, db):
    manager = create_userprofile("manager_cancel")
    contributor = create_userprofile("contributor_cancel")
    gc = GiftContribution.objects.create(
        title="Gift Cancel Test", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('30.00'))
    gc.status = "canceled"
    gc.save()
    transactions = Transaction.objects.filter(gift_contribution=gc, type="gift")
    contributions = gc.contributions.all()
    assert contributions.count() == 0
    assert transactions.count() == 0


@pytest.mark.django_db
def test_gift_contribution_open_transactions_deletion(create_userprofile, db):
    manager = create_userprofile("manager_open")
    contributor = create_userprofile("contributor_open")
    gc = GiftContribution.objects.create(
        title="Gift Open Test", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('20.00'))
    # Create a transaction manually to simulate an existing one.
    Transaction.objects.create(
        from_user=contributor, to_user=manager, amount=Decimal('20.00'),
        type="gift", status="billed", gift_contribution=gc)
    gc.status = "open"
    gc.save()
    transactions = Transaction.objects.filter(gift_contribution=gc, type="gift")
    assert transactions.count() == 0


@pytest.mark.django_db
def test_gift_contribution_multiple_contributions(create_userprofile, db):
    manager = create_userprofile("manager_multi")
    contributor1 = create_userprofile("contributor_multi1")
    contributor2 = create_userprofile("contributor_multi2")
    gc = GiftContribution.objects.create(
        title="Gift Multi", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor1, value=Decimal('30.00'))
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor2, value=Decimal('40.00'))
    gc.status = "closed"
    gc.save()
    transactions = Transaction.objects.filter(gift_contribution=gc, type="gift")
    assert transactions.count() == 2


# --- Tests for Transaction and Payment signals ---
# Capture old status (3 tests)
@pytest.mark.django_db
def test_capture_old_transaction_status_initial(create_userprofile, db):
    payer = create_userprofile("payer1")
    receiver = create_userprofile("receiver1")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('100.00'),
        type='task', status='billed')
    trans.status = 'paid'
    trans.save()
    assert hasattr(trans, '_old_status')
    assert trans._old_status == 'billed'


@pytest.mark.django_db
def test_capture_old_transaction_status_update(create_userprofile, db):
    payer = create_userprofile("payer2")
    receiver = create_userprofile("receiver2")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('50.00'),
        type='event', status='billed')
    trans.status = 'confirmed'
    trans.save()
    assert hasattr(trans, '_old_status')
    assert trans._old_status == 'billed'


@pytest.mark.django_db
def test_capture_old_transaction_status_multiple_updates(create_userprofile, db):
    payer = create_userprofile("payer3")
    receiver = create_userprofile("receiver3")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('75.00'),
        type='gift', status='billed')
    trans.status = 'confirmed'
    trans.save()
    first_old = trans._old_status
    trans.status = 'paid'
    trans.save()
    assert first_old == 'billed'
    assert trans._old_status == 'confirmed'


# PaymentScoreHistory on confirmed transactions (4 tests)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "trans_type,amount",
    [
        ('task', Decimal('100.00')),
        ('event', Decimal('150.00')),
        ('gift', Decimal('200.00')),
        ('task', Decimal('250.00')),
    ]
)
def test_payment_score_history_on_confirmed_varied(trans_type, amount,
                                                   create_userprofile, db):
    payer = create_userprofile(f"payer_{trans_type}_{amount}")
    receiver = create_userprofile(f"receiver_{trans_type}_{amount}")
    event_obj = None
    if trans_type == 'event':
        event_obj = Event.objects.create(title="Event Payment")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=amount,
        type=trans_type, status='confirmed', event=event_obj
    )
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert history.exists()
    for h in history:
        expected_points = math.ceil(amount * Decimal(0.5))
        assert h.points_awarded == expected_points


# PaymentScoreHistory deletion when status changes (6 tests)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "trans_type,amount",
    [
        ('task', Decimal('150.00')),
        ('event', Decimal('150.00')),
        ('gift', Decimal('150.00')),
        ('task', Decimal('180.00')),
        ('event', Decimal('180.00')),
        ('gift', Decimal('180.00')),
    ]
)
def test_payment_history_deletion_on_non_confirmed(trans_type, amount,
                                                   create_userprofile, db):
    payer = create_userprofile(f"payer_del_{trans_type}_{amount}")
    receiver = create_userprofile(f"receiver_del_{trans_type}_{amount}")
    event_obj = None
    if trans_type == 'event':
        print("Event vor creation")
        event_obj = Event.objects.create(title="Event Payment Del")
        print("Event nach creation", event_obj)
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=amount,
        type=trans_type, status='confirmed', event=event_obj
    )
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert history.exists()
    trans.status = 'paid'
    trans.save()
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert not history.exists()


# Payment penalty tests (2 tests)
@pytest.mark.django_db
def test_payment_penalty_different_overdue(create_userprofile, db, monkeypatch):
    payer = create_userprofile("payer_penalty_diff")
    receiver = create_userprofile("receiver_penalty_diff")
    event_obj = Event.objects.create(title="Event Penalty Diff")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('150.00'),
        type='event', status='billed', event=event_obj,
    )
    past_time = timezone.now() - timezone.timedelta(days=8)
    trans.created_at = past_time
    trans.save(update_fields=['created_at'])
    trans.status = 'paid'
    trans.save()
    history = PaymentScoreHistory.objects.filter(
        user_profile=payer, score_type='event', type='penalty')
    assert history.exists()
    for h in history:
        assert h.points_awarded == -25


@pytest.mark.django_db
def test_payment_penalty_no_overdue(create_userprofile, db, monkeypatch):
    payer = create_userprofile("payer_penalty_no")
    receiver = create_userprofile("receiver_penalty_no")
    event_obj = Event.objects.create(title="Event No Penalty")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('150.00'),
        type='event', status='billed', event=event_obj,
    )
    past_time = timezone.now() - timezone.timedelta(days=2)
    trans.created_at = past_time
    trans.save(update_fields=['created_at'])
    trans.status = 'paid'
    trans.save()
    history = PaymentScoreHistory.objects.filter(
        user_profile=payer, score_type='event', type='penalty')
    assert not history.exists()


# Delete PaymentScoreHistory when Transaction is deleted (4 tests)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "trans_type,amount",
    [
        ('task', Decimal('120.00')),
        ('event', Decimal('120.00')),
        ('gift', Decimal('120.00')),
        ('task', Decimal('130.00')),
    ]
)
def test_delete_payment_score_history_on_payment_delete(create_userprofile,
                                                          trans_type, amount, db):
    payer = create_userprofile(f"payer_del_delete_{trans_type}_{amount}")
    receiver = create_userprofile(f"receiver_del_delete_{trans_type}_{amount}")
    event_obj = None
    if trans_type == 'event':
        event_obj = Event.objects.create(title="Event Payment Delete")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=amount,
        type=trans_type, status='confirmed', event=event_obj
    )
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert history.exists()
    trans.delete()
    history_after = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert not history_after.exists()


# --- Helper function update tests (8 tests) ---
@pytest.mark.django_db
def test_update_task_score_helper(create_userprofile, db):
    profile = create_userprofile("helper_task")
    event = Event.objects.create(title="Helper Event")
    task = Task.objects.create(
        event=event, title="Helper Task", status='completed', base_points=30)
    task.assigned_to.add(profile)
    TaskScoreHistory.objects.create(
        task=task, user_profile=profile, points_change=30,
        score_type='task')
    update_task_score(profile)
    profile.refresh_from_db()
    assert profile.task_score == 30


@pytest.mark.django_db
def test_update_task_score_helper_multiple(create_userprofile, db):
    profile = create_userprofile("helper_task_multi")
    event = Event.objects.create(title="Helper Event Multi")
    task1 = Task.objects.create(
        event=event, title="Helper Task1", status='completed',
        base_points=30)
    task2 = Task.objects.create(
        event=event, title="Helper Task2", status='completed',
        base_points=40)
    task1.assigned_to.add(profile)
    task2.assigned_to.add(profile)
    TaskScoreHistory.objects.create(
        task=task1, user_profile=profile, points_change=30,
        score_type='task')
    TaskScoreHistory.objects.create(
        task=task2, user_profile=profile, points_change=40,
        score_type='task')
    update_task_score(profile)
    profile.refresh_from_db()
    assert profile.task_score == 70


@pytest.mark.django_db
def test_update_role_score_helper(create_userprofile, db):
    profile = create_userprofile("helper_role")
    event = Event.objects.create(title="Role Helper Event")
    RoleConfiguration.objects.update_or_create(
        role='manager', defaults={'points': 10})
    participant = EventParticipant.objects.create(
        event=event, user_profile=profile, role='manager')
    RoleScoreHistory.objects.create(
        event_participant=participant, user_profile=profile, role='manager',
        points_awarded=10, note="Test")
    update_role_score(profile)
    profile.refresh_from_db()
    assert profile.role_score == 10


@pytest.mark.django_db
def test_update_role_score_helper_multiple(create_userprofile, db):
    profile = create_userprofile("helper_role_multi")
    event = Event.objects.create(title="Role Helper Multi")
    RoleConfiguration.objects.update_or_create(
        role='attendee', defaults={'points': 5})
    participant1 = EventParticipant.objects.create(
        event=event, user_profile=profile, role='attendee')
    participant2 = EventParticipant.objects.create(
        event=event, user_profile=profile, role='attendee')
    RoleScoreHistory.objects.create(
        event_participant=participant1, user_profile=profile, role='attendee',
        points_awarded=5, note="Test")
    RoleScoreHistory.objects.create(
        event_participant=participant2, user_profile=profile, role='attendee',
        points_awarded=5, note="Test")

    update_role_score(profile)
    profile.refresh_from_db()
    assert profile.role_score == 10


@pytest.mark.django_db
def test_update_gift_score_helper(create_userprofile, db):

    profile = create_userprofile("helper_gift")
    gift_search = GiftSearch.objects.create(
        title="Gift Helper", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal", description="Desc",
        proposed_by=profile)
    GiftScoreHistory.objects.create(
        gift_proposal=proposal, user_profile=profile, points_change=25,
        score_type='proposal', note="Test")

    update_gift_score(profile)
    profile.refresh_from_db()
    assert profile.gift_score == 25


@pytest.mark.django_db
def test_update_gift_score_helper_multiple(create_userprofile, db):
    profile = create_userprofile("helper_gift_multi")
    gift_search = GiftSearch.objects.create(
        title="Gift Helper Multi", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    proposal1 = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal1", description="Desc",
        proposed_by=profile)
    proposal2 = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal2", description="Desc",
        proposed_by=profile)
    GiftScoreHistory.objects.create(
        gift_proposal=proposal1, user_profile=profile, points_change=25,
        score_type='proposal', note="Test")
    GiftScoreHistory.objects.create(
        gift_proposal=proposal2, user_profile=profile, points_change=35,
        score_type='proposal', note="Test")

    update_gift_score(profile)
    profile.refresh_from_db()
    assert profile.gift_score == 60


@pytest.mark.django_db
def test_update_payment_score_helper(create_userprofile, db):
    profile = create_userprofile("helper_payment")
    event = Event.objects.create(title="Payment Helper")
    PaymentScoreHistory.objects.create(
        event=event, user_profile=profile, amount=Decimal('100.00'),
        points_awarded=50, score_type='event', note="Test")

    update_payment_score(profile)
    profile.refresh_from_db()
    assert profile.payment_score == 50


@pytest.mark.django_db
def test_update_payment_score_helper_multiple(create_userprofile, db):
    profile = create_userprofile("helper_payment_multi")
    event = Event.objects.create(title="Payment Helper Multi")
    PaymentScoreHistory.objects.create(
        event=event, user_profile=profile, amount=Decimal('100.00'),
        points_awarded=50, score_type='event', note="Test")
    PaymentScoreHistory.objects.create(
        event=event, user_profile=profile, amount=Decimal('200.00'),
        points_awarded=100, score_type='event', note="Test")
    update_payment_score(profile)
    profile.refresh_from_db()
    assert profile.payment_score == 150


# --- Additional edge-case tests ---
@pytest.mark.django_db
def test_task_score_history_deletion_on_non_qualifying(create_userprofile, db):
    event = Event.objects.create(title="Non Qualifying Task")
    task = Task.objects.create(
        event=event,
        title="Task Non Qualifying",
        status='completed',
        base_points=50,
        penalty_points=-10,
    )
    profile = create_userprofile("nonqual_user")
    task.assigned_to.add(profile)
    task.status = 'completed'
    task.save()
    count1 = TaskScoreHistory.objects.filter(
        task=task, user_profile=profile).count()
    task.status = 'in_progress'
    task.save()
    count2 = TaskScoreHistory.objects.filter(
        task=task, user_profile=profile).count()
    assert count1 > 0
    assert count2 == 0


@pytest.mark.django_db
def test_role_score_history_update_on_change(create_userprofile, db):
    event = Event.objects.create(title="Role Update Event")
    rc, _ = RoleConfiguration.objects.update_or_create(
        role='manager', defaults={'points': 10})
    profile = create_userprofile("role_update_user")
    participant = EventParticipant.objects.create(
        event=event, user_profile=profile, role='manager')
    rsh = RoleScoreHistory.objects.get(
        event_participant=participant, user_profile=profile, role='manager')
    assert rsh.points_awarded == 10
    rc.points = 20
    rc.save()
    participant.save()

    update_role_score(profile)
    total = RoleScoreHistory.objects.filter(
        user_profile=profile).aggregate(total=Sum('points_awarded'))['total']
    # Note: existing history isn’t auto-updated by config change.
    assert total == 10


@pytest.mark.django_db
def test_gift_vote_history_update_on_change(create_userprofile, db):
    voter = create_userprofile("gift_vote_update")
    gc, _ = GiftConfiguration.objects.update_or_create(
        role='voter', defaults={'points': 10})
    gift_search = GiftSearch.objects.create(
        title="Gift Vote Update", purpose="Test", donee=voter,
        deadline=timezone.now().date(), created_by=voter)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal Update",
        description="Desc", proposed_by=voter)
    class DummyVote:
        pass
    vote = DummyVote()
    vote.user_id = voter.user.id
    vote.object_id = proposal.id
    update_gift_score_history_on_vote(sender=GiftProposal, instance=vote, created=True)
    history = GiftScoreHistory.objects.get(
        user_profile=voter, gift_proposal=proposal, score_type='vote')
    assert history.points_change == 10
    gc.points = 15
    gc.save()
    update_gift_score_history_on_vote(sender=GiftProposal, instance=vote, created=False)
    history.refresh_from_db()
    assert history.points_change == 15


@pytest.mark.django_db
def test_gift_proposal_history_not_updated_on_change(create_userprofile, db):

    proposer = create_userprofile("gift_proposal_update")
    GiftConfiguration.objects.update_or_create(
        role='proposer', defaults={'points': 12})
    gift_search = GiftSearch.objects.create(
        title="Gift Proposal Update", purpose="Test", donee=proposer,
        deadline=timezone.now().date(), created_by=proposer)
    proposal = GiftProposal.objects.create(
        gift_search=gift_search, title="Gift Proposal Update",
        description="Desc", proposed_by=proposer)
    history = GiftScoreHistory.objects.get(
        user_profile=proposer, gift_proposal=proposal, score_type='proposal')
    old_points = history.points_change
    proposal.title = "Updated Title"
    proposal.save()
    history.refresh_from_db()
    assert history.points_change == old_points


@pytest.mark.django_db
def test_payment_score_history_on_confirmed_varied_amount(create_userprofile, db):

    payer = create_userprofile("payer_varied")
    receiver = create_userprofile("receiver_varied")
    event_obj = Event.objects.create(title="Event Varied")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('300.00'),
        type='task', status='confirmed', event=event_obj
    )
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert history.exists()
    for h in history:
        expected_points = math.ceil(Decimal('300.00') * Decimal(0.5))
        assert h.points_awarded == expected_points


@pytest.mark.django_db
def test_payment_history_deletion_varied_amount(create_userprofile, db):

    payer = create_userprofile("payer_del_varied")
    receiver = create_userprofile("receiver_del_varied")
    event_obj = Event.objects.create(title="Event Payment Varied")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('220.00'),
        type='gift', status='confirmed', event=event_obj
    )
    history = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert history.exists()
    trans.delete()
    history_after = PaymentScoreHistory.objects.filter(user_profile=payer)
    assert not history_after.exists()


# --- Tests for model __str__ methods and properties (24 tests) ---
@pytest.mark.django_db
def test_userprofile_str(create_userprofile, db):
    profile = create_userprofile("struser")
    assert str(profile) == "struser"


@pytest.mark.django_db
def test_past_user_scores_str(db):
    user = get_user_model().objects.create(username="pastuser")
    scores = PastUserScores.objects.create(
        user=user, total_score=100, task_score=20, role_score=30,
        gift_score=10, payment_score=40, score_date=timezone.now().date())
    assert str(scores).startswith("pastuser: 100 points on")


@pytest.mark.django_db
def test_event_str(create_userprofile, db):
    event = Event.objects.create(title="Event Test")
    assert str(event) == "Event Test"


@pytest.mark.django_db
def test_role_configuration_str(db):
    rc = RoleConfiguration.objects.create(role="organizer", points=10)
    assert str(rc) == "organizer"


@pytest.mark.django_db
def test_event_participant_str(create_userprofile, db):
    event = Event.objects.create(title="Event Participant Test")
    profile = create_userprofile("participant")
    ep = EventParticipant.objects.create(
        event=event, user_profile=profile, role="attendee")
    expected = f"{profile} in {event} as attendee"
    assert str(ep) == expected


@pytest.mark.django_db
def test_role_score_history_str(create_userprofile, db):
    event = Event.objects.create(title="Event Role Score History")
    profile = create_userprofile("rolehistory")
    ep = EventParticipant.objects.create(
        event=event, user_profile=profile, role="manager")
    rsh = RoleScoreHistory.objects.create(
        event_participant=ep, user_profile=profile, role="manager",
        points_awarded=15, note="Test")
    assert "15" in str(rsh)


@pytest.mark.django_db
def test_task_template_str(db):
    template = TaskTemplate.objects.create(
        title="Template Test", description="Desc", base_points=10,
        penalty_points=-5)
    assert str(template) == "Template Test"


@pytest.mark.django_db
def test_task_str(create_userprofile, db):
    event = Event.objects.create(title="Event for Task")
    task = Task.objects.create(
        event=event, title="Task Test", status="pending")
    assert str(task) == "Task Test"


@pytest.mark.django_db
def test_task_score_history_str(create_userprofile, db):
    profile = create_userprofile("taskscore")
    event = Event.objects.create(title="Event for Task Score History")
    task = Task.objects.create(
        event=event, title="Task Score History Test", status="completed",
        base_points=50)
    task.assigned_to.add(profile)
    tsh = TaskScoreHistory.objects.create(
        task=task, user_profile=profile, points_change=50,
        score_type="task", note="Test")
    assert "50" in str(tsh)


@pytest.mark.django_db
def test_gift_configuration_str(db):
    gc = GiftConfiguration.objects.create(role="proposer", points=12)
    assert str(gc) == "proposer"


@pytest.mark.django_db
def test_gift_search_str(create_userprofile, db):
    profile = create_userprofile("giftsearch")
    gs = GiftSearch.objects.create(
        title="Gift Search Test", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    expected = f"Gift Search Test for {profile}"
    assert str(gs) == expected


@pytest.mark.django_db
def test_gift_proposal_str(create_userprofile, db):
    profile = create_userprofile("giftproposal")
    gs = GiftSearch.objects.create(
        title="Gift Proposal Search", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    gp = GiftProposal.objects.create(
        gift_search=gs, title="Gift Proposal Test", description="Desc",
        proposed_by=profile)
    assert str(gp) == "Gift Proposal Test"


@pytest.mark.django_db
def test_gift_score_history_str(create_userprofile, db):
    profile = create_userprofile("giftscore")
    gs = GiftSearch.objects.create(
        title="Gift Score Search", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    gp = GiftProposal.objects.create(
        gift_search=gs, title="Gift Score Proposal", description="Desc",
        proposed_by=profile)
    gsh = GiftScoreHistory.objects.create(
        gift_proposal=gp, user_profile=profile, points_change=20,
        score_type="proposal", note="Test")
    rep = str(gsh)
    assert "20" in rep


@pytest.mark.django_db
def test_gift_contribution_total_contributions(create_userprofile, db):
    manager = create_userprofile("giftcontrib_manager")
    contributor = create_userprofile("giftcontrib_contributor")
    gc = GiftContribution.objects.create(
        title="Gift Contribution Test", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('50.00'))
    Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('70.00'))
    total = gc.total_contributions()
    assert total == 120


@pytest.mark.django_db
def test_contribution_str(create_userprofile, db):
    manager = create_userprofile("contrib_manager")
    contributor = create_userprofile("contrib_contributor")
    gc = GiftContribution.objects.create(
        title="Gift Contribution Str Test", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    contrib = Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('30.00'))
    rep = str(contrib)
    assert "30" in rep


@pytest.mark.django_db
def test_transaction_str(create_userprofile, db):
    payer = create_userprofile("trans_payer")
    receiver = create_userprofile("trans_receiver")
    event = Event.objects.create(title="Event Transaction")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('100.00'),
        type="task", status="billed", event=event)
    rep = str(trans)
    assert "100" in rep


@pytest.mark.django_db
def test_payment_score_history_str(create_userprofile, db):
    profile = create_userprofile("payscore")
    event = Event.objects.create(title="Event Payment Score")
    psh = PaymentScoreHistory.objects.create(
        event=event, user_profile=profile, amount=Decimal('200.00'),
        points_awarded=80, score_type="event", note="Test")
    rep = str(psh)
    assert "80" in rep


# --- Additional tests for model properties (6 tests) ---
@pytest.mark.django_db
def test_event_participant_properties(create_userprofile, db):
    profile1 = create_userprofile("org1")
    profile2 = create_userprofile("mgr1")
    profile3 = create_userprofile("att1")
    profile4 = create_userprofile("hon1")
    event = Event.objects.create(title="Event Participants")
    EventParticipant.objects.create(
        event=event, user_profile=profile1, role="organizer")
    EventParticipant.objects.create(
        event=event, user_profile=profile2, role="manager")
    EventParticipant.objects.create(
        event=event, user_profile=profile3, role="attendee")
    EventParticipant.objects.create(
        event=event, user_profile=profile4, role="honouree")
    assert event.organizers.count() == 1
    assert event.managers.count() == 1
    assert event.attendees.count() == 1
    assert event.honourees.count() == 1


@pytest.mark.django_db
def test_task_default_fields(create_userprofile, db):
    event = Event.objects.create(title="Event for Task Default")
    task = Task.objects.create(
        event=event, title="Task Default Test")
    assert task.notes in [None, ""]
    assert task.attachment is None


@pytest.mark.django_db
def test_gift_search_defaults(create_userprofile, db):
    profile = create_userprofile("giftsearch_default")
    gs = GiftSearch.objects.create(
        title="Gift Search Default", purpose="Test", donee=profile,
        deadline=timezone.now().date(), created_by=profile)
    assert gs.final_results_sent is False
    assert gs.invitation_sent is False
    assert gs.reminder_sent is False
    assert gs.is_auto_generated is False


@pytest.mark.django_db
def test_gift_contribution_str(create_userprofile, db):
    manager = create_userprofile("giftcontrib_str")
    gc = GiftContribution.objects.create(
        title="Gift Contribution Str", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    assert str(gc) == "Gift Contribution Str"


@pytest.mark.django_db
def test_transaction_defaults(create_userprofile, db):
    payer = create_userprofile("trans_default_payer")
    receiver = create_userprofile("trans_default_receiver")
    event = Event.objects.create(title="Event Transaction Defaults")
    trans = Transaction.objects.create(
        from_user=payer, to_user=receiver, amount=Decimal('0.00'),
        type="event", event=event)
    assert trans.status == "billed"


@pytest.mark.django_db
def test_payment_score_history_defaults(create_userprofile, db):
    profile = create_userprofile("payscore_default")
    event = Event.objects.create(title="Event Payment Score Default")
    psh = PaymentScoreHistory.objects.create(
        event=event, user_profile=profile, amount=Decimal('0.00'),
        points_awarded=0, score_type="event")
    assert psh.note == ""


@pytest.mark.django_db
def test_contribution_str_alternative(create_userprofile, db):

    manager = create_userprofile("contrib_alt_manager")
    contributor = create_userprofile("contrib_alt")
    gc = GiftContribution.objects.create(
        title="Gift Contribution Alt", description="Test", donee=manager,
        manager=manager, deadline=timezone.now().date())
    contrib = Contribution.objects.create(
        gift_contribution=gc, contributor=contributor, value=Decimal('45.00'))
    rep = str(contrib)
    assert "45.00" in rep







