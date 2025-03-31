from django import forms
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware
from django.contrib.auth.models import User
from .models import Event, EventParticipant, RoleConfiguration, Task, UserProfile,\
      TaskTemplate, GiftContribution, Contribution, GiftSearch, GiftProposal



# -------------------------------------------------------------
#  Local DateTime Widget
# -------------------------------------------------------------
class LocalDateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'
    
    def format_value(self, value):
        if not value:
            return ''
        # If value is already a string, return it as-is
        if isinstance(value, str):
            return value
        # If value is naive, assume it's in UTC and make it aware
        if is_naive(value):
            value = make_aware(value, timezone.utc)

        # Convert UTC value to local time
        local_value = timezone.localtime(value)
        # Format for HTML5 datetime-local input
        return local_value.strftime('%Y-%m-%dT%H:%M')



# -------------------------------------------------------------
#  Form to add participants to event
# -------------------------------------------------------------
class EventParticipantForm(forms.ModelForm):
    class Meta:
        model = EventParticipant
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Query RoleConfiguration for dynamic choices
        roles = RoleConfiguration.objects.all().values_list('role', 'role')
        self.fields['role'].widget = forms.Select(choices=roles)



# -------------------------------------------------------------
#  Form to update usernamae
# -------------------------------------------------------------
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'style': 'width:200px;'}),
        }



# -------------------------------------------------------------
#  Form to update personal data
# -------------------------------------------------------------
class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['is_inactive', 'birthday', 'onboarding', 'farewell', 'wedding', 'about_me']
        widgets = {
            'is_inactive': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'birthday': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'style': 'width:130px;'}),
            'onboarding': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'style': 'width:130px;'}),
            'farewell': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'style': 'width:130px;'}),
            'wedding': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'style': 'width:130px;'}),
            'about_me': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'style': 'width:600px;'}),
        }



# -------------------------------------------------------------
#  Form to create event
# -------------------------------------------------------------
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'event_type', 'date', 'time', 'location']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'event_type': forms.Select(attrs={'class': 'form-control', 'style': 'width:130px;'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'width:130px;'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'style': 'width:130px;'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }



# -------------------------------------------------------------
#  Form to delete event (only manager)
# -------------------------------------------------------------
class DeleteEventForm(forms.Form):
    confirm = forms.CharField(
        label="Type DEL to confirm deletion",
        max_length=10,
        widget=forms.TextInput(attrs={'placeholder': 'DEL'})
    )

    def clean_confirm(self):
        data = self.cleaned_data.get('confirm', '')
        if data.strip().upper() != "DEL":
            raise forms.ValidationError("You must type DEL to confirm.")
        return data
    


# -------------------------------------------------------------
#  Form to add participant to event
# -------------------------------------------------------------
class AddRoleForm(forms.ModelForm):
    # Use ModelChoiceField that returns role value
    role = forms.ModelChoiceField(
        queryset=RoleConfiguration.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=None,
        to_field_name='role'
    )
    
    class Meta:
        model = EventParticipant
        fields = ['user_profile', 'role']
        widgets = {
            'user_profile': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(AddRoleForm, self).__init__(*args, **kwargs)
        # Only allow active users (is_inactive False)
        self.fields['user_profile'].queryset = UserProfile.objects.filter(is_inactive=False)
        # Ensure role dropdown displays the friendly name
        self.fields['role'].label_from_instance = lambda obj: obj.get_role_display()



# -------------------------------------------------------------
#  Form to create task
# -------------------------------------------------------------
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'assigned_to', 'template', 'title', 'description', 'notes', 'due_date', 'status',
            'is_cost_related', 'budget', 'actual_expenses', 'base_points', 'penalty_points', 'attachment',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'id': 'add-task-title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'add-task-description'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'add-task-notes'}),
            #'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local', 'id': 'add-task-due_date'}),
            'due_date': LocalDateTimeInput(attrs={'class': 'form-control', 'id': 'add-task-due_date'}),
            'status': forms.Select(attrs={'class': 'form-control', 'id': 'add-task-status'}),
            'is_cost_related': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'add-task-is_cost_related'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'id': 'add-task-budget'}),
            'actual_expenses': forms.NumberInput(attrs={'class': 'form-control', 'id': 'add-task-actual_expenses'}),
            'base_points': forms.NumberInput(attrs={'class': 'form-control', 'id': 'add-task-base_points'}),
            'penalty_points': forms.NumberInput(attrs={'class': 'form-control', 'id': 'add-task-penalty_points'}),
            'assigned_to': forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'add-task-assigned_to'}),
            'template': forms.Select(attrs={'class': 'form-control', 'id': 'add-task-template'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'add-task-attachment'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Pop event parameter from kwargs
        event = kwargs.pop('event', None)
        super(TaskForm, self).__init__(*args, **kwargs)

        # Build allowed status choices ('overdue' and 'reminder' not manually)
        allowed_statuses = ['pending', 'in_progress', 'completed']
        self.fields['status'].choices = [
            choice for choice in self.fields['status'].choices if choice[0] in allowed_statuses
        ]

        if event:
            # Refresh for latest updates
            event.refresh_from_db()
            # Set list of possible assignees to allowed users
            allowed_ids = list(
                event.eventparticipant_set.filter(
                    role__in=['manager', 'organizer', 'honouree']
                ).values_list('user_profile__id', flat=True)
            )
            self.fields['assigned_to'].queryset = UserProfile.objects.filter(id__in=allowed_ids)
        else:
            self.fields['assigned_to'].queryset = UserProfile.objects.none()



# -------------------------------------------------------------
#  Form for task editing
# -------------------------------------------------------------
class TaskEditForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'assigned_to','template', 'title', 'description', 'notes', 'due_date', 'status',
            'is_cost_related', 'budget', 'actual_expenses', 'base_points', 'penalty_points', 'attachment',
        ]

        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'id': 'edit-task-title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'edit-task-description'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'edit-task-notes'}),
            #'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local', 'id': 'edit-task-due_date'}),
            'due_date': LocalDateTimeInput(attrs={'class': 'form-control', 'id': 'edit-task-due_date'}),
            'status': forms.Select(attrs={'class': 'form-control', 'id': 'edit-task-status'}),
            'is_cost_related': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'edit-task-is_cost_related'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'id': 'edit-task-budget'}),
            'actual_expenses': forms.NumberInput(attrs={'class': 'form-control', 'id': 'edit-task-actual_expenses'}),
            'base_points': forms.NumberInput(attrs={'class': 'form-control', 'id': 'edit-task-base_points'}),
            'penalty_points': forms.NumberInput(attrs={'class': 'form-control', 'id': 'edit-task-penalty_points'}),
            'assigned_to': forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'edit-task-assigned_to'}),
            'template': forms.Select(attrs={'class': 'form-control', 'id': 'edit-task-template'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'edit-task-attachment'}),
        }

    def __init__(self, *args, **kwargs):
        # Pop event parameter from kwargs
        event = kwargs.pop('event', None)
        event.refresh_from_db()
        super(TaskEditForm, self).__init__(*args, **kwargs)

        # Build allowed status choices ('overdue' and 'reminder' not manually)
        allowed_statuses = ['pending', 'in_progress', 'completed']
        self.fields['status'].choices = [
            choice for choice in self.fields['status'].choices if choice[0] in allowed_statuses
        ]

        if event:
            # Refresh for latest updates
            event.refresh_from_db()
            # Set list of possible assignees to allowed users
            allowed_ids = list(
                event.eventparticipant_set.filter(
                    role__in=['manager', 'organizer', 'honouree']
                ).values_list('user_profile__id', flat=True)
            )
            self.fields['assigned_to'].queryset = UserProfile.objects.filter(id__in=allowed_ids)
        else:
            self.fields['assigned_to'].queryset = UserProfile.objects.none()

        # If POST data doesn't include assigned_to restore the initial value from the instance
        if self.is_bound:
            if not self.data.getlist('assigned_to'):
                if self.instance.pk:
                    # Set initial for assigned_to to the current instance's values
                    self.initial['assigned_to'] = list(self.instance.assigned_to.values_list('id', flat=True))



# -------------------------------------------------------------
#  Form to create task template
# -------------------------------------------------------------
class TaskTemplateForm(forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = ['title', 'description', 'base_points', 'penalty_points', 'task_type']
    


# -------------------------------------------------------------
#  Form for role configuration (event & gift)
# -------------------------------------------------------------
class RoleConfigurationForm(forms.Form):
    # Event roles
    organizer_points = forms.IntegerField(
        label="Organizer Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    attendee_points = forms.IntegerField(
        label="Attendee Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    manager_points = forms.IntegerField(
        label="Manager Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    honouree_points = forms.IntegerField(
        label="Honouree Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )

    # Gift roles
    procurer_points = forms.IntegerField(
        label="Procurer Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    proposer_points = forms.IntegerField(
        label="Proposer Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    voter_points = forms.IntegerField(
        label="Voter Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )
    winner_points = forms.IntegerField(
        label="Winner Points",
        help_text='',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:80px;'})
    )

    def __init__(self, *args, **kwargs):
        # Initial data is provided via a 'role_config' dictionary mapping role to points
        role_config = kwargs.pop('role_config', {})
        super().__init__(*args, **kwargs)
        self.fields['organizer_points'].initial = role_config.get('organizer', 0)
        self.fields['organizer_points'].help_text = role_config.get('organizer_description', '')
        self.fields['attendee_points'].initial = role_config.get('attendee', 0)
        self.fields['attendee_points'].help_text = role_config.get('attendee_description', '')
        self.fields['manager_points'].initial = role_config.get('manager', 0)
        self.fields['manager_points'].help_text = role_config.get('manager_description', '')
        self.fields['honouree_points'].initial = role_config.get('honouree', 0)
        self.fields['honouree_points'].help_text = role_config.get('honouree_description', '')

        self.fields['procurer_points'].initial = role_config.get('procurer', 0)
        self.fields['procurer_points'].help_text = role_config.get('procurer_description', '')
        self.fields['proposer_points'].initial = role_config.get('proposer', 0)
        self.fields['proposer_points'].help_text = role_config.get('proposer_description', '')
        self.fields['voter_points'].initial = role_config.get('voter', 0)
        self.fields['voter_points'].help_text = role_config.get('voter_description', '')
        self.fields['winner_points'].initial = role_config.get('winner', 0)
        self.fields['winner_points'].help_text = role_config.get('winner_description', '')

    def save(self):
        data = self.cleaned_data

        # Save updated values into RoleConfiguration model
        from event_planner.models import RoleConfiguration
        ROLE_CHOICES = ['organizer', 'attendee', 'manager', 'honouree']
        for role in ROLE_CHOICES:
            # Get RoleConfiguration instance for this role
            rc, created = RoleConfiguration.objects.get_or_create(role=role)
            if role == 'organizer':
                rc.points = data.get('organizer_points', 0)
            elif role == 'attendee':
                rc.points = data.get('attendee_points', 0)
            elif role == 'manager':
                rc.points = data.get('manager_points', 0)
            elif role == 'honouree':
                rc.points = data.get('honouree_points', 0)
            rc.save()

        # Save updated values into GiftConfiguration model
        from event_planner.models import GiftConfiguration
        ROLE_CHOICES = ['procurer', 'proposer', 'voter', 'winner']
        for role in ROLE_CHOICES:
            # Get GiftConfiguration instance for this role
            rc, created = GiftConfiguration.objects.get_or_create(role=role)
            if role == 'procurer':
                rc.points = data.get('procurer_points', 0)
            elif role == 'proposer':
                rc.points = data.get('proposer_points', 0)
            elif role == 'voter':
                rc.points = data.get('voter_points', 0)
            elif role == 'winner':
                rc.points = data.get('winner_points', 0)
            rc.save()



# -------------------------------------------------------------
#  Form to create gift contributions
# -------------------------------------------------------------
class GiftContributionForm(forms.ModelForm):
    create_gift_search = forms.BooleanField(
        required=False, 
        label="Automatically create gift search"
    )
    
    class Meta:
        model = GiftContribution
        fields = ['title', 'description', 'donee', 'deadline', 'collection_target', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'donee': forms.Select(attrs={'class': 'form-control', 'style': 'width:200px;'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'width:130px;'}),
            'collection_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'style': 'width:130px;',
                'step': '5.00', 
                'value': '10.00', 
                'min': '0.00', 
                'max': '5000.00',  
                'placeholder': "Enter amount",
            }),
            'status': forms.Select(attrs={'class': 'form-control', 'style': 'width:130px;'}),
        }



# -------------------------------------------------------------
#  Form to contribute for a gift
# -------------------------------------------------------------
class ContributionForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ['value']
        widgets = {
            'value': forms.NumberInput(attrs={
                'class': 'form-control', 
                'style': 'width:200px;',
                'step': '5.00', 
                'value': '10.00', 
                'min': '0.00', 
                'max': '5000.00',  
                'placeholder': "Enter amount",
            }
        )}



# -------------------------------------------------------------
#  Form to create gift search
# -------------------------------------------------------------
class GiftSearchForm(forms.ModelForm):
    class Meta:
        model = GiftSearch
        fields = ['title', 'purpose', 'donee', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'donee': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }



# -------------------------------------------------------------
#  Form to create gift proposal
# -------------------------------------------------------------
class GiftProposalForm(forms.ModelForm):
    class Meta:
        model = GiftProposal
        fields = ['title', 'description', 'photo', 'link']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Gift Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe your gift proposal here...'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
        }


