import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from event_planner.models import *


User = get_user_model()


# -------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------
# IMPORTANT: When a User is created, the signal does not create a UserProfile with fixtures.
@pytest.fixture
def test_user1(db):
    user = User.objects.create_user(username='testuser1', password='password')
    profile = UserProfile.objects.get(user=user)
    profile.save()
    return user

@pytest.fixture
def test_user2(db):
    user = User.objects.create_user(username='testuser2', password='password')
    profile = UserProfile.objects.get(user=user)
    profile.save()
    return user

@pytest.fixture
def test_user3(db):
    user = User.objects.create_user(username='testuser3', password='password')
    profile = UserProfile.objects.get(user=user)
    profile.save()
    return user

@pytest.fixture
def test_user4(db):
    user = User.objects.create_user(username='testuser4', password='password')
    profile = UserProfile.objects.get(user=user)
    profile.save()
    return user

@pytest.fixture
def user_profile1(db, test_user1):
    return UserProfile.objects.get(user=test_user1)

@pytest.fixture
def user_profile2(db, test_user2):
    return UserProfile.objects.get(user=test_user2)

@pytest.fixture
def user_profile3(db, test_user3):
    return UserProfile.objects.get(user=test_user3)

@pytest.fixture
def user_profile4(db, test_user4):
    return UserProfile.objects.get(user=test_user4)

@pytest.fixture
def test_event(db, test_user1):
    return Event.objects.create(
        title='Test Event',
        date=date.today(),
        description='Event description',
        created_by=test_user1,
    )

@pytest.fixture
def role_configurator(db):
    return RoleConfiguration.objects.create(role='organizer', points=10)


# -------------------------------------------------------------
# Tests for UserProfile
# -------------------------------------------------------------
@pytest.mark.django_db
class TestUserProfile:
    def test_signal_creates_user_profile(self, test_user1):
        # Signal creates UserProfile
        profile = UserProfile.objects.get(user=test_user1)
        assert profile.pk is not None

    def test_multiple_instances_different_users(self, test_user1, test_user2):
        # Instances are different
        profile1 = UserProfile.objects.get(user=test_user1)
        profile2 = UserProfile.objects.get(user=test_user2)
        assert profile1 != profile2

    def test_one_to_one_enforcement(self, test_user1):
        # Create UserProfile should error
        with pytest.raises(IntegrityError):
            UserProfile.objects.create(user=test_user1, task_score=10)

    def test_str_returns_username(self, test_user1):
        # Userprofile returns username
        profile = UserProfile.objects.get(user=test_user1)
        assert str(profile) == test_user1.username

    def test_birthday_optional(self, test_user1):
        # Birthday is optional
        profile = UserProfile.objects.get(user=test_user1)
        profile.birthday = None
        profile.save()
        assert profile.birthday is None

    def test_about_me_optional(self, test_user1):
        # About_me is optional
        profile = UserProfile.objects.get(user=test_user1)
        profile.about_me = ''
        profile.save()
        assert profile.about_me == ''

    def test_is_inactive_default_false(self, test_user1):
        # Option is_inactive is false on default
        profile = UserProfile.objects.get(user=test_user1)
        assert profile.is_inactive is False

    def test_profile_field_types(self, test_user1):
        # Field type accepts integers
        profile = UserProfile.objects.get(user=test_user1)
        assert isinstance(profile.total_score, int)
        assert isinstance(profile.task_score, int)
        assert isinstance(profile.role_score, int)
        assert isinstance(profile.gift_score, int)

    def test_total_score_zero(self, test_user1):
        # total_score is zero on default
        profile = UserProfile.objects.get(user=test_user1)
        profile.total_score = 0
        assert profile.total_score == 0

    def test_default_scores(self, test_user1):
        # Scores are zero on default
        profile = UserProfile.objects.get(user=test_user1)
        assert profile.task_score == 0
        assert profile.role_score == 0
        assert profile.gift_score == 0
        assert profile.total_score_past == 0
        assert profile.task_score_past == 0
        assert profile.role_score_past == 0
        assert profile.gift_score_past == 0

    def test_update_task_score(self, test_user1):
        # Update of task score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score = 10
        profile.save()
        assert profile.task_score == 10
        assert profile.total_score == 10

    def test_update_role_score(self, test_user1):
        # Update of role score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.role_score = 10
        profile.save()
        assert profile.role_score == 10
        assert profile.total_score == 10

    def test_update_gift_score(self, test_user1):
        # Update of gift score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.gift_score = 10
        profile.save()
        assert profile.gift_score == 10
        assert profile.total_score == 10

    def test_update_total_score(self, test_user1):
        # Update of total score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.total_score = 10
        profile.save()
        assert profile.total_score == 0

    def test_update_all_scores(self, test_user1):
        # Update of all scores calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score = 10
        profile.role_score = 10
        profile.gift_score = 10
        profile.save()
        assert profile.total_score == 30

    def test_update_negative_scores(self, test_user1):
        # Update of all scores negative calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score = 10
        profile.role_score = -5
        profile.gift_score = -10
        profile.save()
        assert profile.total_score == -5

    def test_update_total_score(self, test_user1):
        # Update of total_score is overwritten
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score = 10
        profile.role_score = 10
        profile.gift_score = 10
        profile.total_score = 10
        profile.save()
        assert profile.total_score == 30

    def test_update_task_score_past(self, test_user1):
        # Update of task score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score_past = 10
        profile.save()
        assert profile.task_score_past == 10
        assert profile.total_score_past == 10

    def test_update_role_score_past(self, test_user1):
        # Update of role score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.role_score_past = 10
        profile.save()
        assert profile.role_score_past == 10
        assert profile.total_score_past == 10

    def test_update_gift_score_past(self, test_user1):
        # Update of gift score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.gift_score_past = 10
        profile.save()
        assert profile.gift_score_past == 10
        assert profile.total_score_past == 10

    def test_update_total_score_past(self, test_user1):
        # Update of total score calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.total_score_past = 10
        profile.save()
        assert profile.total_score_past == 0

    def test_update_all_scores_past(self, test_user1):
        # Update of all scores calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score_past = 10
        profile.role_score_past = 10
        profile.gift_score_past = 10
        profile.save()
        assert profile.total_score_past == 30

    def test_update_negative_scores_past(self, test_user1):
        # Update of all scores negative calculates total_score
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score_past = 10
        profile.role_score_past = -5
        profile.gift_score_past = -10
        profile.save()
        assert profile.total_score_past == -5

    def test_update_total_score(self, test_user1):
        # Update of total_score is overwritten
        profile = UserProfile.objects.get(user=test_user1)
        profile.task_score = 10
        profile.role_score = 10
        profile.gift_score = 10
        profile.total_score = 10
        profile.save()
        assert profile.total_score == 30

    def test_update_about_me(self, test_user1):
        # Update of about_me works
        profile = UserProfile.objects.get(user=test_user1)
        profile.about_me = "pdated about me"
        profile.save()
        assert profile.about_me == "pdated about me"

    def test_update_is_inactive(self, test_user1):
        # Update of is_inactive works
        profile = UserProfile.objects.get(user=test_user1)
        profile.is_inactive = True
        profile.save()
        assert profile.is_inactive is True

    def test_profile_update_multiple_fields(self, test_user1):
        # Update multiple fields of user profile
        profile = UserProfile.objects.get(user=test_user1)
        profile.about_me = "Updated about me"
        profile.is_inactive = True
        profile.task_score = 7
        profile.save()
        assert profile.about_me == "Updated about me"
        assert profile.is_inactive is True
        assert profile.task_score == 7
        assert profile.role_score == 0
        assert profile.gift_score == 0
        assert profile.total_score == 7

    def test_profile_full_clean_method(self, test_user1):
        # Test validation logic
        profile = UserProfile.objects.get(user=test_user1)
        profile.full_clean()



# -------------------------------------------------------------
# Tests for PastUserScores
# -------------------------------------------------------------
@pytest.mark.django_db
class TestPastUserScores:
    def test_create_valid_past_user_scores(self, test_user1):
        # Create valid record
        scores = PastUserScores.objects.create(
            user=test_user1,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        assert scores.pk is not None

    def test_str_returns_expected(self, test_user1):
        # Instance returns user, points and date
        today = date.today()
        scores = PastUserScores.objects.create(
            user=test_user1,
            task_score=7,
            role_score=4,
            gift_score=3,
            total_score=15,
            score_date=today
        )
        expected = f"{test_user1}: 15 points on {today}"
        assert str(scores) == expected

    def test_unique_together_enforcement(self, test_user1):
        # Duplicate record should error
        today = date.today()
        PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=today
        )
        scores_duplicate = PastUserScores(
            user=test_user1,
            total_score=20,
            task_score=10,
            role_score=6,
            gift_score=4,
            score_date=today
        )
        with pytest.raises(IntegrityError):
            scores_duplicate.save()

    def test_required_user_field(self):
        # Create record without user should error
        with pytest.raises(IntegrityError):
            PastUserScores.objects.create(
                total_score=10,
                task_score=5,
                role_score=3,
                gift_score=2,
                score_date=date.today()
            )

    def test_required_score_date(self, test_user1):
        # Create record without date should error 
        with pytest.raises(IntegrityError):
            PastUserScores.objects.create(
                user=test_user1,
                total_score=10,
                task_score=5,
                role_score=3,
                gift_score=2,
            )

    def test_default_scores(self, test_user1):
        # Scores are zero on default
        scores = PastUserScores.objects.create(
            user=test_user1,
            score_date=date.today()
        )
        assert scores.total_score == 0
        assert scores.task_score == 0
        assert scores.role_score == 0
        assert scores.gift_score == 0

    def test_profile_field_types(self, test_user1):
        # Field type accepts integers
        profile = UserProfile.objects.get(user=test_user1)
        assert isinstance(profile.total_score, int)
        assert isinstance(profile.task_score, int)
        assert isinstance(profile.role_score, int)
        assert isinstance(profile.gift_score, int)

    def test_update_scores(self, test_user1):
        # Update of scores works
        scores = PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        scores.total_score = 20
        scores.save()
        assert scores.total_score == 20

    def test_multiple_entries_different_dates(self, test_user1):
        # Instances are different
        scores1 = PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        scores2 = PastUserScores.objects.create(
            user=test_user1,
            total_score=15,
            task_score=7,
            role_score=4,
            gift_score=3,
            score_date=date.today() + timedelta(days=1)
        )
        assert scores1 != scores2

    def test_multiple_entries_same_dates(self, test_user1):
        # Instances with same user and date should error
        scores1 = PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        with pytest.raises(IntegrityError):
            PastUserScores.objects.create(
            user=test_user1,
            total_score=15,
            task_score=7,
            role_score=4,
            gift_score=3,
            score_date=date.today()
        )

    def test_multiple_entries_different_users(self, test_user1, test_user2):
        # Scores for different users should differ
        scores1 = PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        scores2 = PastUserScores.objects.create(
            user=test_user2,
            total_score=15,
            task_score=7,
            role_score=4,
            gift_score=3,
            score_date=date.today()
        )
        assert scores1.user != scores2.user

    def test_score_date_is_date(self, test_user1):
        # Score date is valid date
        scores = PastUserScores.objects.create(
            user=test_user1,
            total_score=10,
            task_score=5,
            role_score=3,
            gift_score=2,
            score_date=date.today()
        )
        assert isinstance(scores.score_date, date)

    def test_string_format_includes_date(self, test_user1):
        # Instance returns date
        today = date.today()
        scores = PastUserScores.objects.create(
            user=test_user1,
            total_score=12,
            task_score=6,
            role_score=4,
            gift_score=2,
            score_date=today
        )
        assert str(scores).endswith(str(today))

    def test_save_and_retrieve(self, test_user1):
        # Saved record can be retrieved
        scores = PastUserScores.objects.create(
            user=test_user1,
            total_score=18,
            task_score=9,
            role_score=5,
            gift_score=4,
            score_date=date.today()
        )
        retrieved = PastUserScores.objects.get(pk=scores.pk)
        assert retrieved.total_score == 18



# -------------------------------------------------------------
# Tests for Event
# -------------------------------------------------------------
@pytest.mark.django_db
class TestEvent:
    def test_create_event_valid(self, test_user1):
        # Create valid record
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            created_by=test_user1,
        )
        assert event.pk is not None
 
    def test_update_event_description(self, test_event):
        # Description is set correct
        test_event.description = 'Updated description'
        test_event.save()
        assert test_event.description == 'Updated description'

    def test_string_returns_expected(self, test_user1):
        # Instance returns title
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            created_by=test_user1,
        )
        assert str(event) == 'New Event'

    def test_optional_time_field(self, test_user1):
        # Date is optional
        event = Event.objects.create(
            title='New Event',
            description='A valid event',
            created_by=test_user1,
        )
        assert event.time is None

    def test_optional_location_field(self, test_user1):
        # Location is optional
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            created_by=test_user1,
        )
        assert event.location == ''

    def test_default_event_type(self, test_user1):
        # Event type is 'other' on default
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            created_by=test_user1,
        )
        assert event.event_type == 'other'

    def test_valid_event_type_choices(self, test_user1):
        # Event type is set correct
        event = Event.objects.create(
            title='Birthday Event',
            date=date.today(),
            description='A valid event',
            event_type='birthday',
            created_by=test_user1,
        )
        event.full_clean()
        assert event.event_type == 'birthday'

    def test_invalid_event_type_choices(self, test_user1):
        # Event type is not in choices
        event = Event(
            title='Invalid Event Type',
            date=date.today(),
            description='A valid event',
            event_type='invalid',
            created_by=test_user1,
        )
        with pytest.raises(ValidationError):
            event.full_clean()

    def test_default_status(self, test_user1):
        # Status is 'planned' on default
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            created_by=test_user1,
        )
        assert event.status == 'planned'

    def test_valid_status_choices(self, test_user1):
        # Status is set correct
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            description='A valid event',
            status='active',
            created_by=test_user1,
        )
        event.full_clean()
        assert event.status == 'active'

    def test_invalid_status_choices(self, test_user1):
        # Status is not in choices
        event = Event(
            title='New Event',
            date=date.today(),
            status='unknown',
            created_by=test_user1,
        )
        with pytest.raises(ValidationError):
            event.full_clean()

    def test_cost_breakdown_json_field(self, test_user1):
        # Cost breakdown accepts JSON
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            cost_breakdown={"food": 100, "venue": 200},
            created_by=test_user1,
        )
        assert event.cost_breakdown == {"food": 100, "venue": 200}

    def test_created_at_auto_set(self, test_user1):
        # Created_at is set automatically on creation
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            created_by=test_user1,
        )
        assert event.created_at is not None

    def test_updated_at_auto_set(self, test_user1):
        # Updated_at is set automatically on creation/change
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            created_by=test_user1,
        )
        assert event.updated_at is not None

    def test_created_by_relationship(self, test_user1):
        # Created_by is set correctly
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            created_by=test_user1,
        )
        assert event.created_by == test_user1

    def test_updated_by_relationship(self, test_user1):
        # Updated_by is set correctly
        event = Event.objects.create(
            title='New Event',
            date=date.today(),
            created_by=test_user1,
            updated_by=test_user1,
        )
        assert event.updated_by == test_user1

    def test_add_event_participant_organizer_and_query(self, test_event, user_profile1):
        # Add event participant of role 'organizer' and query attribute
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        organizers = test_event.organizers.all()
        assert participant in organizers

    def test_add_event_participant_manager_and_query(self, test_event, user_profile1):
        # Add event participant of role 'manager' and query attribute
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        managers = test_event.managers.all()
        assert participant in managers

    def test_add_event_participant_attendee_and_query(self, test_event, user_profile1):
        # Add event participant of role 'attendee' and query attribute
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        attendees = test_event.attendees.all()
        assert participant in attendees

    def test_add_event_participant_honouree_and_query(self, test_event, user_profile1):
        # Add event participant of role 'honouree' and query attribute
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='honouree')
        honourees = test_event.honourees.all()
        assert participant in honourees

    def test_event_multiple_participants_different_roles(self, test_event, user_profile1, user_profile2, user_profile3, user_profile4):
        # Add muliple event participants to different roles and query all
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='manager')
        participant3 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile3, 
            role='attendee')
        participant4 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile4, 
            role='honouree')       
        participants = test_event.eventparticipant_set.all()
        assert participant1 in participants and participant2 in participants and participant3 in participants and participant4 in participants

    def test_event_multiple_participants_same_role(self, test_event, user_profile1, user_profile2, user_profile3, user_profile4):
        # Add muliple event participants to same role and query attribute
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='organizer')
        participant3 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile3, 
            role='organizer')
        participant4 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile4, 
            role='organizer')       
        participants = test_event.organizers.all()
        assert participant1 in participants and participant2 in participants and participant3 in participants and participant4 in participants

    def test_event_multiple_participants_same_role_count(self, test_event, user_profile1, user_profile2, user_profile3, user_profile4):
        # Add muliple event participants to same role and query attribute
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile3, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile4, 
            role='organizer')       
        participants = test_event.organizers.all()
        assert participants.count() == 4

    def test_remove_event_participant(self, test_event, user_profile1, user_profile2):
        # Remove one of two participants
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='manager')
        participant1.delete()
        managers = test_event.managers.all()
        assert participant1 not in managers
        assert participant2 in managers

    def test_event_participant_string_expected(self, test_event, user_profile1):
        # Event participant returns name, event, role
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        expected = f"{user_profile1} in {test_event} as attendee"
        assert str(participant) == expected



# -------------------------------------------------------------
# Tests for EventParticipant
# -------------------------------------------------------------
@pytest.mark.django_db
class TestEventParticipant:
    def test_create_valid_event_participant(self, test_event, user_profile1):
        # Create valid record
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        assert participant.pk is not None

    def test_string_returns_expected(self, test_event, user_profile1):
        # Instance returns user, event, role
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        expected = f"{user_profile1} in {test_event} as organizer"
        assert str(participant) == expected

    def test_unique_together_constraint(self, test_event, user_profile1):
        # Same role of user in event should error
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        with pytest.raises(IntegrityError):
            EventParticipant.objects.create(
                event=test_event, 
                user_profile=user_profile1, 
                role='attendee')

    def test_eventparticipant_relationship_event(self, test_event, user_profile1):
        # Event in eventparticipant should equal event
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        assert participant.event == test_event

    def test_eventparticipant_relationship_user_profile(self, test_event, user_profile1):
        # Assigned participant is eventparticipant of event
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='honouree')
        assert participant.user_profile == user_profile1

    def test_eventparticipant_joined_at_auto(self, test_event, user_profile1):
        # Eventparticipant is joined at event
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        assert participant.joined_at is not None

    def test_multiple_roles_for_same_event_user_different(self, test_event, user_profile1):
        # User can have different roles in same event
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        assert participant1 != participant2

    def test_remove_event_participant_single_role(self, test_event, user_profile1):
        # Removed eventparticipant from one role does not effect other roles in event
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        participant1.delete()
        assert EventParticipant.objects.filter(pk=participant2.pk).exists()

    def test_remove_event_participant_all_roles(self, test_event, user_profile1):
        # Removed eventparticipant from all roles in event
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        participants = EventParticipant.objects.filter(user_profile=user_profile1)
        participants.delete()
        assert not EventParticipant.objects.filter(user_profile=user_profile1).exists()

    def test_query_eventparticipant_by_role(self, test_event, user_profile1):
        # Query one eventparticipant by role 
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participants = EventParticipant.objects.filter(
            event=test_event, 
            role='organizer')
        assert participant in participants

    def test_query_eventparticipants_by_role(self, test_event, user_profile1, user_profile2, user_profile3, user_profile4):
        # Query multiple eventparticipants by role 
        participant1 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        participant2 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='organizer')
        participant3 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile3, 
            role='organizer')
        participant4 = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile4, 
            role='organizer')
        participants = EventParticipant.objects.filter(
            event=test_event, 
            role='organizer')
        assert participant1 in participants and participant2 in participants and participant3 in participants and participant4 in participants

    def test_query_eventparticipants_count(self, test_event, user_profile1, user_profile2, user_profile3, user_profile4):
        # Query multiple eventparticipant by role 
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile2, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile3, 
            role='organizer')
        EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile4, 
            role='organizer')
        participants = EventParticipant.objects.filter(event=test_event, role='organizer').count()
        assert participants == 4

    def test_eventparticipant_related_event(self, test_event, user_profile1):
        # Get eventparticipant via related event
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        participants = test_event.eventparticipant_set.all()
        assert participant in participants

    def test_eventparticipant_update_role(self, test_event, user_profile1):
        # Update role of eventparticipant
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        participant.role = 'manager'
        participant.save()
        assert participant.role == 'manager'

    def test_eventparticipant_save_and_retrieve(self, test_event, user_profile1):
        # Set and get eventparticipant
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='honouree')
        retrieved = EventParticipant.objects.get(pk=participant.pk)
        assert retrieved.role == 'honouree'

    def test_eventparticipant_error_on_null_fields(self, test_event):
        # Eventparticipant needs userprofile
        with pytest.raises(IntegrityError):
            EventParticipant.objects.create(event=test_event, role='attendee')

    def test_joined_at_auto_set(self, test_event, user_profile1):
        # Created_at is set automatically on creation
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        assert participant.joined_at is not None



# -------------------------------------------------------------
# Tests for RoleConfiguration
# -------------------------------------------------------------
@pytest.mark.django_db
class TestRoleConfiguration:
    def test_create_valid_role_configuration(self):
        # Create valid instance
        role_configuration = RoleConfiguration.objects.create(role='attendee', points=0)
        assert role_configuration.pk is not None

    def test_string_returns_role(self):
        # Instance with valid role
        role_configuration = RoleConfiguration.objects.create(role='manager', points=5)
        assert str(role_configuration) == 'manager'

    def test_unique_role_enforcement(self):
        # Role must be unique
        RoleConfiguration.objects.create(role='honouree', points=2)
        with pytest.raises(IntegrityError):
            RoleConfiguration.objects.create(role='honouree', points=3)

    def test_valid_points_value(self):
        # Test validation logic
        role_configuration = RoleConfiguration.objects.create(role='organizer', points=10)
        role_configuration.full_clean()
        assert role_configuration.points >= 0

    def test_invalid_points_value(self):
        # Role must have positive points
        role_configuration = RoleConfiguration(role='attendee', points=-5)
        with pytest.raises(ValidationError):
            role_configuration.full_clean()

    def test_update_points(self):
        # Points of a role can be updated
        role_configuration = RoleConfiguration.objects.create(role='manager', points=5)
        role_configuration.points = 8
        role_configuration.save()
        assert role_configuration.points == 8

    def test_update_role(self):
        # Role can be updated
        role_configuration = RoleConfiguration.objects.create(role='honouree', points=2)
        role_configuration.role = 'manager'
        role_configuration.save()
        assert role_configuration.role == 'manager'

    def test_create_role_configuration_for_all_roles(self):
        # Create multiple valid instances
        roles = ['organizer', 'attendee', 'manager', 'honouree']
        for role in roles:
            role_configuration = RoleConfiguration.objects.create(role=role, points=0)
            assert role_configuration.role == role

    def test_role_choice_invalid(self):
        # Role is not in choices raises error
        role_configuration = RoleConfiguration(role='invalid_role', points=0)
        with pytest.raises(ValidationError):
            role_configuration.full_clean()

    def test_duplicate_role_creation_raises_error(self):
        # Role must be unique
        RoleConfiguration.objects.create(role='organizer', points=10)
        with pytest.raises(IntegrityError):
            RoleConfiguration.objects.create(role='organizer', points=15)

    def test_points_default_value(self):
        # Points are 0 on default
        role_configuration = RoleConfiguration.objects.create(role='manager')
        assert role_configuration.points == 0

    def test_role_configuration_clean_method(self):
        # Test validation logic
        role_configuration = RoleConfiguration(role='attendee', points=0)
        role_configuration.full_clean() 
        assert role_configuration.points == 0

    def test_multiple_role_configurations(self):
        # Instances are not the same
        role_configuration1 = RoleConfiguration.objects.create(role='organizer', points=10)
        role_configuration2 = RoleConfiguration.objects.create(role='attendee', points=0)
        assert role_configuration1 != role_configuration2



# -------------------------------------------------------------
# Tests for RoleScoreHistory
# -------------------------------------------------------------
@pytest.mark.django_db
class TestRoleScoreHistory:
    def test_create_valid_role_score_history(self, test_event, user_profile1):
        # Create valid record
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=5,
            note='Great job'
        )
        assert history.pk is not None

    def test_string_returns_expected(self, test_event, user_profile1):
        # History returne user, points, time
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='attendee',
            points_awarded=3,
            note='Well done'
        )
        expected = f"{user_profile1} awarded 3 for attendee on {history.timestamp.strftime('%Y-%m-%d %H:%M')}"
        assert str(history) == expected

    def test_auto_timestamp_set(self, test_event, user_profile1):
        # Timestamp is set automatically
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=4,
            note=''
        )
        assert history.timestamp is not None

    def test_role_field_preservation(self, test_event, user_profile1):
        # Role is preserved in instance
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='honouree')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='honouree',
            points_awarded=2,
            note='Congrats'
        )
        assert history.role == 'honouree'

    def test_points_awarded_value(self, test_event, user_profile1):
        # Points are preserved in instance
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='attendee',
            points_awarded=7,
            note=''
        )
        assert history.points_awarded == 7

    def test_note_optional(self, test_event, user_profile1):
        # Note is optional
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=5
        )
        assert history.note == ''

    def test_relationship_eventparticipant(self, test_event, user_profile1):
        # Event participant is participant in role history
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='organizer',
            points_awarded=6,
            note=''
        )
        assert history.event_participant == participant

    def test_relationship_user_profile(self, test_event, user_profile1):
        # User profile is profile in role history
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='attendee',
            points_awarded=3,
            note=''
        )
        assert history.user_profile == user_profile1

    def test_multiple_role_score_history_entries(self, test_event, user_profile1):
        # User can have multiple history entries
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history1 = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=5,
            note='First'
        )
        history2 = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=4,
            note='Second'
        )
        query = RoleScoreHistory.objects.filter(event_participant=participant)
        assert history1 in query and history2 in query

    def test_update_role_score_history(self, test_event, user_profile1):
        # Update history points
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='attendee',
            points_awarded=3,
            note=''
        )
        history.points_awarded = 8
        history.save()
        assert history.points_awarded == 8

    def test_retrieve_role_score_history(self, test_event, user_profile1):
        # Create and retrieve history instance
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='organizer')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='organizer',
            points_awarded=5,
            note=''
        )
        retrieved = RoleScoreHistory.objects.get(pk=history.pk)
        assert retrieved.points_awarded == 5

    def test_role_score_history_string_expected(self, test_event, user_profile1):
        # Instance returns user, points, time
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=9,
            note='Excellent'
        )
        expected = f"{user_profile1} awarded 9 for manager on {history.timestamp.strftime('%Y-%m-%d %H:%M')}"
        assert str(history) == expected

    def test_negative_points_awarded_allowed(self, test_event, user_profile1):
        # Negative points in history allowed
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='attendee')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='attendee',
            points_awarded=-2,
            note='Penalty'
        )
        assert history.points_awarded == -2

    def test_timestamp_format(self, test_event, user_profile1):
        # Datetime has correct format
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='honouree')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='honouree',
            points_awarded=3,
            note=''
        )
        assert ':' in history.timestamp.strftime('%Y-%m-%d %H:%M')

    def test_role_score_history_integrity(self, test_event, user_profile1):
        # Eventparticipant is participant
        participant = EventParticipant.objects.create(
            event=test_event, 
            user_profile=user_profile1, 
            role='manager')
        history = RoleScoreHistory.objects.create(
            event_participant=participant,
            user_profile=user_profile1,
            role='manager',
            points_awarded=5,
            note='Good'
        )
        assert history.event_participant.pk == participant.pk



# -------------------------------------------------------------
# Tests for TaskTemplate
# -------------------------------------------------------------
@pytest.mark.django_db
class TestTaskTemplate:
    def test_create_valid_task_template(self):
        # Create valid instance
        template = TaskTemplate.objects.create(
            title='Template 1',
            description='A task template',
            base_points=10,
            penalty_points=0,
            task_type='event'
        )
        assert template.pk is not None

    def test_str_returns_title(self):
        # Template has correct title
        template = TaskTemplate.objects.create(
            title='Template Title',
            description='Desc',
            base_points=5,
            penalty_points=0,
            task_type='gift'
        )
        assert str(template) == 'Template Title'

    def test_base_points_default(self):
        # Template has correct base points
        template = TaskTemplate.objects.create(
            title='Base Points Test',
            description='',
            base_points=10,
            penalty_points=0,
            task_type='event'
        )
        assert template.base_points == 10

    def test_penalty_points_default(self):
        # Template has correct penalty points
        template = TaskTemplate.objects.create(
            title='Penalty Test',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        assert template.penalty_points == 0

    def test_penalty_points_validator_valid(self):
        # Validation test correct
        template = TaskTemplate.objects.create(
            title='Valid Penalty',
            description='',
            base_points=10,
            penalty_points=0,
            task_type='event'
        )
        template.full_clean()

    def test_penalty_points_validator_invalid(self):
        # Validation test raises error
        template = TaskTemplate(
            title='Invalid Penalty',
            description='',
            base_points=10,
            penalty_points=5,  # Should be <= 0
            task_type='event'
        )
        with pytest.raises(ValidationError):
            template.full_clean()

    def test_task_type_default(self):
        # Task type default is event
        template = TaskTemplate.objects.create(
            title='Type Default',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        assert template.task_type == 'event'

    def test_valid_task_type_choices(self):
        # Task type is in choices
        template = TaskTemplate.objects.create(
            title='Gift Template',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='gift'
        )
        template.full_clean()
        assert template.task_type == 'gift'

    def test_invalid_task_type_choice(self):
        # Task type is not in choices
        template = TaskTemplate(
            title='Invalid TaskType',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='invalid'
        )
        with pytest.raises(ValidationError):
            template.full_clean()

    def test_description_blank_allowed(self):
        # Description is optional
        template = TaskTemplate.objects.create(
            title='No Desc',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        assert template.description == ''

    def test_title_required(self):
        # Title is required
        template = TaskTemplate(
            title='',
            description='',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        with pytest.raises(ValidationError):
            template.full_clean()

    def test_update_task_template(self):
        # Update of instance works correct
        template = TaskTemplate.objects.create(
            title='Update Test',
            description='Old desc',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        template.description = 'New desc'
        template.save()
        assert template.description == 'New desc'

    def test_task_template_save_and_retrieve(self):
        # Create and retrieve instance
        template = TaskTemplate.objects.create(
            title='Retrieve Test',
            description='Test',
            base_points=5,
            penalty_points=0,
            task_type='gift'
        )
        retrieved = TaskTemplate.objects.get(pk=template.pk)
        assert retrieved.title == 'Retrieve Test'

    def test_multiple_task_templates(self):
        # Two instances are not the same
        template1 = TaskTemplate.objects.create(
            title='Template A',
            description='A',
            base_points=5,
            penalty_points=0,
            task_type='event'
        )
        template2 = TaskTemplate.objects.create(
            title='Template B',
            description='B',
            base_points=8,
            penalty_points=0,
            task_type='gift'
        )
        assert template1 != template2



# -------------------------------------------------------------
# Tests for Task
# -------------------------------------------------------------
@pytest.mark.django_db
class TestTask:
    def test_create_valid_task(self, test_event):
        # Create valid instance
        task = Task.objects.create(
            event=test_event,
            title='Task 1',
            description='Task description',
            base_points=10,
            penalty_points=0
        )
        assert task.pk is not None

    def test_string_returns_expected(self, test_event):
        # Instance returns title 
        task = Task.objects.create(
            event=test_event,
            title='Task 1',
            description='Task description',
            base_points=10,
            penalty_points=0
        )
        assert str(task) == 'Task 1'

    def test_event_relationship(self, test_event):
        # Event in task is event of task
        task = Task.objects.create(
            event=test_event,
            title='Task 1',
            description='Task description',
            base_points=10,
            penalty_points=0,
        )
        assert task.event == test_event

    def test_template_relationship(self, test_event):
        # Template in task is task template
        template = TaskTemplate.objects.create(
            title='Task 1',
            description='Task description',
            base_points=10,
            penalty_points=0,
            task_type='event'
        )
        task = Task.objects.create(
            event=test_event,
            title='Task with Template',
            description='',
            base_points=10,
            penalty_points=0,
            template=template
        )
        assert task.template == template

    def test_assigned_to_add_single(self, test_event, user_profile1):
        # User assigned to task is preserved
        task = Task.objects.create(
            event=test_event,
            title='Assign Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        assert user_profile1 in task.assigned_to.all()

    def test_assigned_to_add_multiple(self, test_event, user_profile1, user_profile2):
        # Users assigned to task are preserved
        task = Task.objects.create(
            event=test_event,
            title='Assign Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        task.assigned_to.add(user_profile2)
        users = task.assigned_to.all()
        assert user_profile1 in users and user_profile2 in users 

    def test_assigned_to_remove_single(self, test_event, user_profile1):
        # User removed from task is not assigned to task
        task = Task.objects.create(
            event=test_event,
            title='Remove Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        task.assigned_to.remove(user_profile1)
        assert user_profile1 not in task.assigned_to.all()

    def test_assigned_to_remove_multiple(self, test_event, user_profile1, user_profile2):
        # User removed from task is not assigned to task, other users still assigned
        task = Task.objects.create(
            event=test_event,
            title='Remove Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        task.assigned_to.add(user_profile2)
        task.assigned_to.remove(user_profile1)
        users = task.assigned_to.all()
        assert user_profile1 not in users and user_profile2 in users

    def test_assigned_to_query_single(self, test_event, user_profile1):
        # Query returns assigned user
        task = Task.objects.create(
            event=test_event,
            title='Query Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        query = task.assigned_to.filter(pk=user_profile1.pk)
        assert query.exists()

    def test_assigned_to_query_multiple(self, test_event, user_profile1, user_profile2):
        # Query returns assigned user
        task = Task.objects.create(
            event=test_event,
            title='Query Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        task.assigned_to.add(user_profile2)
        query = task.assigned_to.filter(pk=user_profile1.pk)
        assert user_profile1 in query and user_profile2 not in query

    def test_due_date_optional(self, test_event):
        # Due date is optional
        task = Task.objects.create(
            event=test_event,
            title='Due Date Task',
            description='',
            base_points=10,
            penalty_points=0,
            due_date=None
        )
        assert task.due_date is None

    def test_status_default(self, test_event):
        # Status is pending on default
        task = Task.objects.create(
            event=test_event,
            title='Status Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert task.status == 'pending'

    def test_valid_status_choices(self, test_event):
        # Status is in choices
        task = Task.objects.create(
            event=test_event,
            title='In Progress Task',
            description='',
            base_points=10,
            penalty_points=0,
            status='in_progress'
        )
        task.full_clean()
        assert task.status == 'in_progress'

    def test_invalid_status_choice(self, test_event):
        # Status is not in choices
        task = Task(
            event=test_event,
            title='Bad Status Task',
            description='',
            base_points=10,
            penalty_points=0,
            status='unknown'
        )
        with pytest.raises(ValidationError):
            task.full_clean()

    def test_is_cost_related_default_false(self, test_event):
        # is_cost_related is false on default
        task = Task.objects.create(
            event=test_event,
            title='Cost Related Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert task.is_cost_related is False

    def test_budget_field_optional(self, test_event):
        # Budget is optional
        task = Task.objects.create(
            event=test_event,
            title='Budget Task',
            description='',
            base_points=10,
            penalty_points=0,
        )
        assert task.budget is None

    def test_actual_expenses_field_optional(self, test_event):
        # Actual expenses are optional
        task = Task.objects.create(
            event=test_event,
            title='Expenses Task',
            description='',
            base_points=10,
            penalty_points=0,
        )
        assert task.actual_expenses is None

    def test_base_points_validator_valid(self, test_event):
        # Base points must be positive
        task = Task.objects.create(
            event=test_event,
            title='Base Points',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.full_clean()
        assert task.base_points == 10

    def test_base_points_validator_failure(self, test_event):
        # Base points must be positive
        task = Task(
            event=test_event,
            title='Base Points',
            description='',
            base_points=-10,
            penalty_points=-5 
        )
        with pytest.raises(ValidationError):
            task.full_clean()

    def test_penalty_points_validator_valid(self, test_event):
        # Penalty points must be negative
        task = Task(
            event=test_event,
            title='Penalty Points',
            description='',
            base_points=10,
            penalty_points=-5 
        )
        task.full_clean()
        assert task.penalty_points == -5

    def test_penalty_points_validator_failure(self, test_event):
        # Penalty points must be negative
        task = Task(
            event=test_event,
            title='Penalty Points',
            description='',
            base_points=10,
            penalty_points=5 
        )
        with pytest.raises(ValidationError):
            task.full_clean()

    def test_points_awarded_optional(self, test_event):
        # Points awarded are empty on creation
        task = Task.objects.create(
            event=test_event,
            title='Points Awarded Task',
            description='',
            base_points=10,
            penalty_points=0,
        )
        assert task.points_awarded is None

    def test_completed_at_default(self, test_event):
        # Completed_at is empty on default
        task = Task.objects.create(
            event=test_event,
            title='Completed Task',
            description='',
            base_points=10,
            penalty_points=0,
        )
        assert task.completed_at is None

    def test_completed_at_set(self, test_event):
        # Completed_at is set automatically on completion
        task = Task.objects.create(
            event=test_event,
            title='Completed Task',
            description='',
            base_points=10,
            penalty_points=0,
            status = 'completed'
        )
        assert task.completed_at is not None

    def test_points_awarded_completion(self, test_event):
        # Completed_at is set automatically on completion
        task = Task.objects.create(
            event=test_event,
            title='Completed Task',
            description='',
            base_points=10,
            penalty_points=0,
            status = 'completed'
        )
        assert task.points_awarded == 10

    def test_created_at_auto_set(self, test_event):
        # Task created_at is set automatically
        task = Task.objects.create(
            event=test_event,
            title='Created At Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert task.created_at is not None

    def test_updated_at_auto_set(self, test_event):
        # Task updated_at is set automatically
        task = Task.objects.create(
            event=test_event,
            title='Updated Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert task.updated_at is not None

    def test_update_task_status(self, test_event):
        # Status is updated correctly
        task = Task.objects.create(
            event=test_event,
            title='Update Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.status = 'completed'
        task.save()
        assert task.status == 'completed'

    def test_add_multiple_assigned_users(self, test_event, user_profile1, user_profile2):
        # Assign multiple user at once
        task = Task.objects.create(
            event=test_event,
            title='Multi Assign Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1, user_profile2)
        assert user_profile1 in task.assigned_to.all() and user_profile2 in task.assigned_to.all()

    def test_many_to_many_assigned_to_count(self, test_event, user_profile1):
        # Count assigned users
        task = Task.objects.create(
            event=test_event,
            title='Multi Assign Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.assigned_to.add(user_profile1)
        query = task.assigned_to.all()
        assert query.count() == 1

    def test_task_update_title(self, test_event):
        # Update task title
        task = Task.objects.create(
            event=test_event,
            title='Old Title',
            description='',
            base_points=10,
            penalty_points=0
        )
        task.title = 'New Title'
        task.save()
        assert task.title == 'New Title'

    def test_task_update_description(self, test_event):
        # Update task description
        task = Task.objects.create(
            event=test_event,
            title='Desc Update Task',
            description='Old Desc',
            base_points=10,
            penalty_points=0
        )
        task.description = 'New Desc'
        task.save()
        assert task.description == 'New Desc'

    def test_task_cost_fields_with_values(self, test_event):
        # Create cost related task
        task = Task.objects.create(
            event=test_event,
            title='Cost Fields Task',
            description='',
            base_points=10,
            penalty_points=0,
            is_cost_related=True,
            budget=Decimal('100.00'),
            actual_expenses=Decimal('80.00')
        )
        assert task.is_cost_related is True
        assert task.budget == Decimal('100.00')
        assert task.actual_expenses == Decimal('80.00')

    def test_task_template_nullable(self, test_event):
        # Create task without template
        task = Task.objects.create(
            event=test_event,
            title='No Template Task',
            description='',
            base_points=10,
            penalty_points=0,
            template=None
        )
        assert task.template is None

    def test_task_string_exspected(self, test_event):
        # Instance returns title
        task = Task.objects.create(
            event=test_event,
            title='Format Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert str(task) == 'Format Task'

    def test_task_notes(self, test_event):
        # Notes saved correctly
        task = Task.objects.create(
            event=test_event,
            title='Notes Task',
            description='',
            base_points=10,
            penalty_points=0,
            notes='Some extra notes'
        )
        assert task.notes == 'Some extra notes'

    def test_task_relationship_integrity(self, test_event):
        # Event in task is event of task
        task = Task.objects.create(
            event=test_event,
            title='Relationship Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        assert task.event.pk == test_event.pk

    def test_task_query_by_event(self, test_event):
        # Filter task by event
        task = Task.objects.create(
            event=test_event,
            title='Query Event Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        query = Task.objects.filter(event=test_event)
        assert task in query



# -------------------------------------------------------------
# Tests for TaskScoreHistory
# -------------------------------------------------------------
@pytest.mark.django_db
class TestTaskScoreHistory:
    def test_create_valid_task_score_history(self, test_event, user_profile1):
        # Create valid record
        task = Task.objects.create(
            event=test_event,
            title='Score Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=10,
            score_type='task',
            note='Good job'
        )
        assert history.pk is not None

    def test_str_returns_expected(self, test_event, user_profile1):
        # Instance returns user, task, points, time
        task = Task.objects.create(
            event=test_event,
            title='Score Format Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=5,
            score_type='penalty',
            note='Late submission'
        )
        expected = f"{user_profile1} | Task: {task} | 5 pts on {history.timestamp.strftime('%Y-%m-%d %H:%M')}"
        assert str(history) == expected

    def test_points_change_field(self, test_event, user_profile1):
        # Points change is updated correct
        task = Task.objects.create(
            event=test_event,
            title='Change Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=7,
            score_type='task',
            note=''
        )
        assert history.points_change == 7

    def test_valid_score_type_choices(self, test_event, user_profile1):
        # Score type is in choices
        task = Task.objects.create(
            event=test_event,
            title='Score Type Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=3,
            score_type='other',
            note=''
        )
        history.full_clean()
        assert history.score_type == 'other'

    def test_invalid_score_type_choice(self, test_event, user_profile1):
        # Score type is not in choices
        task = Task.objects.create(
            event=test_event,
            title='Invalid Score Type',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory(
            task=task,
            user_profile=user_profile1,
            points_change=3,
            score_type='invalid',
            note=''
        )
        with pytest.raises(ValidationError):
            history.full_clean()

    def test_timestamp_auto_set(self, test_event, user_profile1):
        # Timestamp is sst automatically
        task = Task.objects.create(
            event=test_event,
            title='Timestamp Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=4,
            score_type='task',
            note=''
        )
        assert history.timestamp is not None

    def test_note_optional(self, test_event, user_profile1):
        # Note is optional
        task = Task.objects.create(
            event=test_event,
            title='Note Optional Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=2,
            score_type='task'
        )
        assert history.note == ''

    def test_relationship_task(self, test_event, user_profile1):
        # Task in history is task of task
        task = Task.objects.create(
            event=test_event,
            title='Rel Task Score',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=6,
            score_type='penalty',
            note=''
        )
        assert history.task == task

    def test_relationship_user_profile(self, test_event, user_profile1):
        # User in history is user of task
        task = Task.objects.create(
            event=test_event,
            title='User Task Score',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=5,
            score_type='task',
            note=''
        )
        assert history.user_profile == user_profile1

    def test_multiple_task_score_history_entries(self, test_event, user_profile1):
        # History can have task and penalty entries for one task
        task = Task.objects.create(
            event=test_event,
            title='Multi Score Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history1 = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=3,
            score_type='task',
            note='First'
        )
        history2 = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=-1,
            score_type='penalty',
            note='Late'
        )
        query = TaskScoreHistory.objects.filter(task=task)
        assert history1 in query and history2 in query

    def test_update_task_score_history(self, test_event, user_profile1):
        # Update of history record is correct
        task = Task.objects.create(
            event=test_event,
            title='Update Score Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=4,
            score_type='task',
            note=''
        )
        history.points_change = 8
        history.save()
        assert history.points_change == 8

    def test_query_task_score_history_by_user(self, test_event, user_profile1):
        # Query returns record of user
        task = Task.objects.create(
            event=test_event,
            title='Query Score Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=5,
            score_type='other',
            note=''
        )
        query = TaskScoreHistory.objects.filter(user_profile=user_profile1)
        assert history in query

    def test_negative_points_change_allowed(self, test_event, user_profile1):
        # Points can be negative for type 'penalty'
        task = Task.objects.create(
            event=test_event,
            title='Negative Points Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=-3,
            score_type='penalty',
            note='Penalty'
        )
        assert history.points_change == -3

    def test_task_score_history_string_expected(self, test_event, user_profile1):
        # Instance returns user, task, points, time
        task = Task.objects.create(
            event=test_event,
            title='String Format Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=7,
            score_type='task',
            note='Well done'
        )
        expected = f"{user_profile1} | Task: {task} | 7 pts on {history.timestamp.strftime('%Y-%m-%d %H:%M')}"
        assert str(history) == expected

    def test_task_score_history_integrity(self, test_event, user_profile1):
        # Primary key of history task is primary key of task
        task = Task.objects.create(
            event=test_event,
            title='Integrity Score Task',
            description='',
            base_points=10,
            penalty_points=0
        )
        history = TaskScoreHistory.objects.create(
            task=task,
            user_profile=user_profile1,
            points_change=5,
            score_type='task',
            note=''
        )
        assert history.task.pk == task.pk








