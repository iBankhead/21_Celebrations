from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import EventListView, EventPlannedView, EventFinalView



urlpatterns = [
    # Dashboard
    path('', views.index, name='index'), # UNITTEST

    # Delete account
    path('user/delete/', views.delete_account, name='account_delete'),
    
    # Display leaderboard
    path('leaderboard/', views.leaderboard, name='leaderboard'),    # UNITTEST

    # Display calendar
    path('calendar/', views.calendar_view, name='calendar_view'),        # UNITTEST

    # List upcoming events
    path('events/', EventListView.as_view(), name='event_list'),    # UNITTEST

    # List planned events
    path('events_planned/', EventPlannedView.as_view(), name='event_planned'),      # UNITTEST

    # List completed/billed/paid events
    path('events_final/', EventFinalView.as_view(), name='event_final'),    # UNITTEST

    # List all transactions of event
    path('events/<int:event_id>/transactions/', views.event_transactions, name='event_transactions'),       # UNITTEST

    # Delete planned event (only managers)
    path('events/delete/<int:event_id>/', views.delete_event, name='delete_event'),     # UNITTEST

    # Create a new event
    path('events/create/', views.create_event, name='create_event'),    # UNITTEST
    
    # Edit event details
    path('events/<int:event_id>/edit/', views.edit_event_detail, name='edit_event_detail'), # UNITTEST

    # Add new role to event
    path('events/<int:event_id>/add_role/', views.add_role, name='add_role'),   # UNITTEST

    # Delete role from event
    path('events/<int:event_id>/delete_role/', views.delete_role, name='delete_role'),  # UNITTEST

    # Add new task to event
    path('events/<int:event_id>/add_task/', views.add_task, name='add_task'),   # UNITTEST

    # Edit task of event
    path('events/<int:event_id>/edit_task/', views.edit_task, name='edit_task'),    # UNITTEST

    # Load task data endpoint
    path('events/<int:event_id>/get_task/<int:task_id>/', views.get_task_data, name='get_task_data'),

    # Delete task from event
    path('events/<int:event_id>/delete_task/', views.delete_task, name='delete_task'),  # UNITTEST

    # Settle costs of events
    path('event/<int:event_id>/clearing/', views.clearing_view, name='clearing_view'),  # UNITTEST

    # Display task template
    path('task-templates/', views.task_template_list, name='task_template_list'),       # UNITTEST

    # Create task template
    path('create-task-template/', views.create_task_template, name='create_task_template'),     # UNITTEST

    # Edit task template
    path('edit-task-template/<int:template_id>/', views.edit_task_template, name='edit_task_template'),     # UNITTEST

    # Delete task template
    path('delete-task-template/<int:template_id>/', views.delete_task_template, name='delete_task_template'),       # UNITTEST

    # Attend event in dashboard
    path('events/attend/<int:event_id>/', views.attend_event, name='attend_event'),     # UNITTEST

    # Decline event in dashboard
    path('events/decline/<int:event_id>/', views.decline_event, name='decline_event'),       # UNITTEST

    # Update task status in dashboard
    path('tasks/update/<int:task_id>/', views.update_task_status, name='update_task_status'),   # UNITTEST

    # Handles the POST from the modal form in open_tasks.html
    path('tasks/update-detail/', views.update_task_detail, name='update_task_detail'),      # UNITTEST

    # Writes template defaults into task
    path('get-template-defaults/<int:template_id>/', views.get_template_defaults, name='get_template_defaults'),

    # Update payment status in dashboard
    path('payments/update/<int:transaction_id>/', views.update_payment, name='update_payment'),

    # Creates gift search
    path('gifts/create/', views.create_gift_search, name='create_gift_search'),

    # Displays list of open gift searches
    path('gifts/open/', views.gift_list, name='gift_list'),

    # Displays gift search detail (proposals)
    path('gifts/<int:search_id>/', views.gift_search_detail, name='gift_search_detail'),

    # Vote for gift proposal
    path('gifts/vote/<int:proposal_id>/<str:vote_type>/', views.vote_gift_proposal, name='vote_gift_proposal'),

    # Displays list of closed gift searches
    path('gifts/closed/', views.closed_gift_list, name='closed_gift_list'),

    # Creates gift contribution
    path('gift_contribution/create/', views.create_gift_contribution, name='create_gift_contribution'),

    # Displays list of open gift contributions
    path('gift_contribution/', views.gift_contribution_list, name='gift_contribution_list'),

    # Shows details of gift contribution
    path('gift_contribution/<int:pk>/', views.gift_contribution_detail, name='gift_contribution_detail'),

    # Shows contribution dialog
    path('gift_contribution/<int:pk>/contribute/', views.contribute_to_gift, name='contribute_to_gift'),

    # Shows list of contributors
    path('gift_contribution/<int:pk>/list/', views.list_gift_contributions, name='list_gift_contributions'),

    # Displays list of closed gift searches (only manager)
    path('gift_contribution/closed/', views.closed_contribution_list, name='closed_contribution_list'),

    # Shows dialog for updating of status or deadline (only manager)
    path('gift_contribution/update/', views.update_gift_contribution, name='update_gift_contribution'),

    # Manage role configuration
    path('role-configuration/', views.role_configuration, name='role_configuration'),

    # Manage job settings
    path('job-settings/', views.job_settings, name='job_settings'),

    # Manage general settings
    path('general-settings/', views.general_settings, name='general_settings'),

    # Manage users
    path('admin/users/', views.user_management, name='user_management'),

    # Manage events
    path('admin/events/', views.event_management, name='event_management'),

    # Manage gift contributions
    path('gift_contribution/management/', views.gift_contribution_management, name='gift_contribution_management'),

    # Manage gift searches
    path('admin/gift_searches/', views.gift_search_management, name='gift_search_management'),

    # Manage personal data
    path('personal-data/', views.personal_data, name='personal_data'),

    # Attend event from email
    path('attend_event/<int:event_id>/', views.attend_from_mail, name='attend_from_mail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



