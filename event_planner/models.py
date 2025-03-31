from decimal import Decimal
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from vote.models import VoteModel




# -------------------------------------------------------------
# Use Django's user model
# -------------------------------------------------------------
User = settings.AUTH_USER_MODEL



# -------------------------------------------------------------
# Model for extending the user properties
# -------------------------------------------------------------
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    birthday = models.DateField(null=True, blank=True)
    onboarding = models.DateField(null=True, blank=True)
    farewell = models.DateField(null=True, blank=True)
    wedding = models.DateField(null=True, blank=True)

    about_me = models.TextField(blank=True)
    is_inactive = models.BooleanField(default=False)  

    total_score =  models.IntegerField(default=0)
    task_score = models.IntegerField(default=0)
    role_score = models.IntegerField(default=0) 
    gift_score = models.IntegerField(default=0)
    payment_score = models.IntegerField(default=0)

    total_score_past = models.IntegerField(default=0)
    task_score_past = models.IntegerField(default=0)
    role_score_past = models.IntegerField(default=0) 
    gift_score_past = models.IntegerField(default=0)
    payment_score_past = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username



# -------------------------------------------------------------
# Model that stores historical values of user scores
# -------------------------------------------------------------
class PastUserScores(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_score = models.IntegerField(default=0)
    task_score = models.IntegerField(default=0)
    role_score = models.IntegerField(default=0) 
    gift_score = models.IntegerField(default=0)
    payment_score = models.IntegerField(default=0)
    score_date = models.DateField()

    class Meta:
        unique_together = ('user', 'score_date')
        
    def __str__(self):
        return f"{self.user}: {self.total_score} points on {self.score_date}"
    


# -------------------------------------------------------------
# Model with details for an event including status, tracking and participant roles
# -------------------------------------------------------------
class Event(models.Model): 
    # Define different event types
    EVENT_TYPES = [
        ('birthday', 'Birthday'),
        ('farewell', 'Farewell'),
        ('milestone', 'Milestone'),
        ('onboarding', 'Onboarding'),
        ('team_building', 'Team Building'),
        ('wedding', 'Wedding'),
        ('other', 'Other'),
    ]
    # Define different statuses for event
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('billed', 'Billed'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),        
    ]
    
    # Attributes of event like event title, event date, ...
    title = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, default='other')
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    invitation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    deferral_sent = models.BooleanField(default=False)

    # Auto-generated events vs manually creatde events ans status tracking of events
    is_auto_generated = models.BooleanField(default=False)  
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_event'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_event'
    )

    # Use a JSONField for cost breakdown data
    cost_breakdown = models.JSONField(null=True, blank=True)
    
    # Participants can have multiple roles in an event
    participants = models.ManyToManyField(UserProfile, through='EventParticipant', related_name='events')
    
    @property
    def organizers(self):
        return self.eventparticipant_set.filter(role='organizer').select_related('user_profile')

    @property
    def managers(self):
        return self.eventparticipant_set.filter(role='manager').select_related('user_profile')

    @property
    def attendees(self):
        return self.eventparticipant_set.filter(role='attendee').select_related('user_profile')

    @property
    def honourees(self):
        return self.eventparticipant_set.filter(role='honouree').select_related('user_profile')
    
    def __str__(self):
        return self.title



# -------------------------------------------------------------
# Model for Event Role Configuration 
# -------------------------------------------------------------
class RoleConfiguration(models.Model):
    # Define different roles for events
    ROLE_CHOICES = [
        ('organizer', 'Organizer'),
        ('attendee', 'Attendee'),
        ('manager', 'Manager'),
        ('honouree', 'Honouree'),
    ]
    
    # Attributes of event role
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    points = models.IntegerField(validators=[MinValueValidator(0)], default=0, help_text="Points awarded for taking this role.")

    def __str__(self):
        # return f"{self.get_role_display()}: {self.points} points"
        return self.role



# -------------------------------------------------------------
# Model that connects an event with its participants while storing additional information about each participant’s role
# -------------------------------------------------------------
class EventParticipant(models.Model):
    # Attributes of participation like event title, role, ...
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    role = models.CharField(max_length=50)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('event', 'user_profile', 'role')
        
    def __str__(self):
        return f"{self.user_profile} in {self.event} as {self.role}"



# -------------------------------------------------------------
# Model which stores history of scores per role of a participant (through EventParticipant)
# -------------------------------------------------------------
class RoleScoreHistory(models.Model):
    # Define different roles for events
    ROLE_CHOICES = [
        ('organizer', 'Organizer'),
        ('attendee', 'Attendee'),
        ('manager', 'Manager'),
        ('honouree', 'Honouree'),
    ]

    # Marks score as role score
    type = models.CharField(max_length=10, default='role', editable=False)

    # Relations to event and user profile
    event_participant = models.ForeignKey('EventParticipant', on_delete=models.CASCADE, related_name='role_score_history')
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='role_score_history')
    
    # Attributes of role score
    role = models.CharField(max_length=50, help_text="The role the user took in the event.")
    points_awarded = models.IntegerField(help_text="Points awarded for this role.")
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, help_text="Optional details about the score awarded.")

    def __str__(self):
        return f"{self.user_profile} awarded {self.points_awarded} for {self.role} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Ensure type is always set to constant
        self.type = 'role'
        super().save(*args, **kwargs)



# -------------------------------------------------------------
# Model for predefined task that can be used as a template in task definition (through Task model)
# -------------------------------------------------------------
class TaskTemplate(models.Model):
    # Define different roles for events
    TASK_TYPES = [
        ('event', 'Event'),
        ('gift', 'Gift'),
    ]
    # Attributes of task template like title, description, ...
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_points =  models.IntegerField(
        validators=[MinValueValidator(0)], 
        default=0,
        help_text="Default base points for this task template."
    )
    penalty_points = models.IntegerField(
        validators=[MaxValueValidator(0)],
        default=0,
        help_text="Default penalty points for this task template."
    )
    # Attributes of event role
    task_type = models.CharField(max_length=50, choices=TASK_TYPES, default='event')

    def __str__(self):
        return self.title



# -------------------------------------------------------------
# Model which associates tasks with an event and users. It can optionally be based on a task template (through TaskTemplate model)
# -------------------------------------------------------------
class Task(models.Model):
    # Relations of a task
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ManyToManyField('UserProfile', related_name='tasks', blank=True)

    template = models.ForeignKey(
        TaskTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tasks',
        help_text="If set, this task was created from a predefined template."
    )

    # Attributes of task like title, description, ...
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Field for additional notes or comments
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional comments or details about the task."
    )

    # Status tracking of a task
    due_date = models.DateTimeField(null=True, blank=True)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('reminder', 'Reminder Sent'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Current status of the task."
    )
    
    # Optional: Cost-related fields of a task
    is_cost_related = models.BooleanField(
        default=False,
        help_text="Indicates if this task incurs costs."
    )
    budget = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Budget allocated for this task."
    )
    actual_expenses = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Actual expenses incurred for this task."
    )
    # Optional: File attachment for a task like receipts, plans, etc.
    attachment = models.FileField(
        upload_to='task_attachments/', 
        null=True, 
        blank=True,
        help_text="Optional attachment, e.g. receipts or planning documents."
    )

    # Score-related fields for a task
    base_points = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0, 
        help_text="Base points for completing the task on time."
    )
    penalty_points = models.IntegerField(
        validators=[MaxValueValidator(0)],
        default=0, 
        help_text="Penalty points for late or non-completion of the task."
    )
    points_awarded = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Final points awarded after completion (may include penalties for overdue tasks)."
    )
    completed_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Timestamp when the task was completed."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title



# -------------------------------------------------------------
# Model which stores history of score changes per task and user (through Task and UserProfile)
# -------------------------------------------------------------
class TaskScoreHistory(models.Model):
    # Define different score types for events
    SCORE_TYPE_CHOICES = [
        ('task', 'Task'),
        ('penalty', 'Penalty'),
        ('other', 'Other'),
    ]
    
    # Marks score as task score
    type = models.CharField(max_length=10, default='task', editable=False)
    
    # Relations of the score history
    task = models.ForeignKey('Task', on_delete=models.CASCADE, related_name='score_history')
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='score_history')
    
    # Attributes of the score history like title, description, ...
    points_change = models.IntegerField(help_text="Change in points (positive for awards, negative for penalties).")
    score_type = models.CharField(
        max_length=20, 
        choices=SCORE_TYPE_CHOICES, 
        default='task',
        help_text="Type of score change."
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(
        blank=True, 
        help_text="Optional note explaining the score change (e.g. 'Completed on time', 'Overdue penalty', etc.)"
    )
    
    def __str__(self):
        return f"{self.user_profile} | Task: {self.task} | {self.points_change} pts on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Ensure type is always set to constant
        self.type = 'task'
        super().save(*args, **kwargs)



# -------------------------------------------------------------
# Model for Gift Configuration 
# -------------------------------------------------------------
class GiftConfiguration(models.Model):
    # Define different roles for gifts
    ROLE_CHOICES = [
        ('procurer', 'Procurer'),
        ('proposer', 'Proposer'),
        ('voter', 'Voter'),
        ('winner', 'Winner'),
    ]
    
    # Attributes of the gift role
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    points = models.IntegerField(validators=[MinValueValidator(0)], default=0, help_text="Points awarded for taking this role.")

    def __str__(self):
        # return f"{self.get_role_display()}: {self.points} points"
        return self.role



# -------------------------------------------------------------
# Model which stores meta information for gift search
# -------------------------------------------------------------
class GiftSearch(models.Model):
    title = models.CharField(max_length=50)
    purpose = models.CharField(max_length=255)
    donee = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_searches_received')
    deadline = models.DateField()
    created_by = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_searches_created')
    created_at = models.DateTimeField(auto_now_add=True)
    
    final_results_sent = models.BooleanField(default=False) 
    invitation_sent = models.BooleanField(default=False) 
    reminder_sent = models.BooleanField(default=False) 
    is_auto_generated = models.BooleanField(default=False)  

    def __str__(self):
        return f"{self.title} for {self.donee}"



# -------------------------------------------------------------
# Model which stores proposals for gift searches with voting
# -------------------------------------------------------------
class GiftProposal(VoteModel, models.Model):
    gift_search = models.ForeignKey(GiftSearch, on_delete=models.CASCADE, related_name='proposals')
    title = models.CharField(max_length=255)
    description = models.TextField()
    photo = models.ImageField(upload_to='gift_photos/', blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    proposed_by = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_proposals')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title



# -------------------------------------------------------------
# Model which stores history of gift scores per gift and user (through Gift and UserProfile)
# -------------------------------------------------------------
class GiftScoreHistory(models.Model):
    # Define different score types for gifts
    SCORE_TYPE_CHOICES = [
        ('proposal', 'Proposal'),
        ('vote', 'Vote'),
        ('winner', 'Winner'),
    ]
    
    # Marks score as gift score
    type = models.CharField(max_length=10, default='gift', editable=False)
    
    # Relations of the score history
    gift_proposal = models.ForeignKey('GiftProposal', on_delete=models.CASCADE, related_name='score_history')
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_score_history')
    
    # Attributes of the score history like title, description, ...
    points_change = models.IntegerField(help_text="Change in points (positive for awards, negative for penalties).")
    score_type = models.CharField(
        max_length=20, 
        choices=SCORE_TYPE_CHOICES, 
        default='proposal',
        help_text="Type of score change."
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(
        blank=True, 
        help_text="Optional note explaining the score change (e.g. 'Proposed the winning gift', etc.)"
    )

    def __str__(self):
        if self.score_type == 'proposal':
            return f"{self.user_profile} awarded {self.points_change} pts for proposing '{self.gift_proposal}' at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
        elif self.score_type == 'vote':
            return f"{self.user_profile} awarded {self.points_change} pts for the vote on '{self.gift_proposal}' at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
        else:
            return f"{self.user_profile} awarded {self.points_change} pts for the winning proposal of '{self.gift_proposal}' at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Ensure type is always set to constant
        self.type = 'gift'
        super().save(*args, **kwargs)



# -------------------------------------------------------------
#  Model which stores meta information for gift contributions
# -------------------------------------------------------------
class GiftContribution(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('canceled', 'Canceled'),
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    donee = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_contributions_received')
    manager = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='gift_contributions_managed')
    deadline = models.DateField()
    collection_target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # When gift search is created automatically
    gift_search = models.OneToOneField('GiftSearch', on_delete=models.SET_NULL, null=True, blank=True)

    invitation_sent = models.BooleanField(default=False) 
    reminder_sent = models.BooleanField(default=False) 
    is_auto_generated = models.BooleanField(default=False)  

    def total_contributions(self):
        total = self.contributions.aggregate(total=Sum('value'))['total']
        return total if total else 0

    def contribution_count(self):
        return self.contributions.count()

    def __str__(self):
        return self.title



# -------------------------------------------------------------
#  Model with stores contribution commitments of users for a gift contribution
# -------------------------------------------------------------
class Contribution(models.Model):
    gift_contribution = models.ForeignKey(GiftContribution, on_delete=models.CASCADE, related_name='contributions')
    contributor = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='contributions')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.contributor} contributed {self.value}"



# -------------------------------------------------------------
# Model which stores payment transactions
# -------------------------------------------------------------
class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('task', 'Task'),
        ('event', 'Event'),
        ('gift', 'Gift'),
    ]
    STATUS_CHOICES = [
        ('billed', 'Billed'),
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed'),
    ]

    from_user = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='transactions_sent')
    to_user = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='transactions_received')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='event')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='billed')
    task = models.ForeignKey('Task', on_delete=models.CASCADE, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    gift_search = models.ForeignKey(GiftSearch, on_delete=models.CASCADE, null=True, blank=True)
    gift_contribution = models.ForeignKey(GiftContribution, on_delete=models.CASCADE, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('UserProfile', on_delete=models.CASCADE, null=True, blank=True,)

    def __str__(self):
        if self.type == 'task':
            return f"{self.from_user} → {self.to_user}: {self.amount} ({self.task.title})"
        if self.type == 'event':
            return f"{self.from_user} → {self.to_user}: {self.amount} ({self.event.title})"
        if self.type == 'gift':
            if self.gift_search:
                return f"{self.from_user} → {self.to_user}: {self.amount} ({self.gift_search.title})"
            elif self.gift_contribution:
                return f"{self.from_user} → {self.to_user}: {self.amount} ({self.gift_contribution.title})"
            else:
                return f"{self.from_user} → {self.to_user}: {self.amount}"                
            

# -------------------------------------------------------------
# Model which stores history of payment scores per payment and user (through Transaction and UserProfile)
# -------------------------------------------------------------
class PaymentScoreHistory(models.Model):
    # Define different types for payments
    SCORE_TYPE_CHOICES = [
        ('task', 'Task'),
        ('event', 'Event'),
        ('gift', 'Gift'),
    ]

    # Marks score as task score
    type = models.CharField(max_length=10, default='payment', editable=True)

    # Relations to event and user profile
    task = models.ForeignKey('Task', on_delete=models.CASCADE, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    gift_search = models.ForeignKey(GiftSearch, on_delete=models.CASCADE, null=True, blank=True)
    gift_contribution = models.ForeignKey(GiftContribution, on_delete=models.CASCADE, null=True, blank=True)
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE)
    
    # Attributes of the role score
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    points_awarded = models.IntegerField(help_text="Points awarded for this payment.")
    score_type = models.CharField(
        max_length=20, 
        choices=SCORE_TYPE_CHOICES, 
        default='event',
        help_text="Type of score change."
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, help_text="Optional details about the score awarded.")

    def __str__(self):
        if self.type == 'penalty':
            if self.score_type == 'task':
                return f"{self.user_profile} deducted {self.points_awarded} for '{self.task.title}' {self.note}"
            if self.score_type == 'event':
                return f"{self.user_profile} deducted {self.points_awarded} for '{self.event.title}' {self.note}"
            if self.score_type == 'gift':
                return f"{self.user_profile} deducted {self.points_awarded} for '{self.gift_contribution.title}' {self.note}"
        else:
            if self.score_type == 'task':
                return f"{self.user_profile} awarded {self.points_awarded} for {self.task.title} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
            if self.score_type == 'event':
                return f"{self.user_profile} awarded {self.points_awarded} for {self.event.title} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
            if self.score_type == 'gift':
                return f"{self.user_profile} awarded {self.points_awarded} for {self.gift_contribution.title} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
