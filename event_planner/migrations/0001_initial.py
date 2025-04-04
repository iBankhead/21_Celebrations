# Generated by Django 4.2.19 on 2025-03-28 18:57

from decimal import Decimal
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('event_type', models.CharField(choices=[('birthday', 'Birthday'), ('farewell', 'Farewell'), ('milestone', 'Milestone'), ('onboarding', 'Onboarding'), ('team_building', 'Team Building'), ('wedding', 'Wedding'), ('other', 'Other')], default='other', max_length=50)),
                ('date', models.DateField(blank=True, null=True)),
                ('time', models.TimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('invitation_sent', models.BooleanField(default=False)),
                ('reminder_sent', models.BooleanField(default=False)),
                ('deferral_sent', models.BooleanField(default=False)),
                ('is_auto_generated', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('planned', 'Planned'), ('active', 'Active'), ('completed', 'Completed'), ('billed', 'Billed'), ('paid', 'Paid'), ('canceled', 'Canceled')], default='planned', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cost_breakdown', models.JSONField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_event', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='EventParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=50)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event_planner.event')),
            ],
        ),
        migrations.CreateModel(
            name='GiftConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('procurer', 'Procurer'), ('proposer', 'Proposer'), ('voter', 'Voter'), ('winner', 'Winner')], max_length=50, unique=True)),
                ('points', models.IntegerField(default=0, help_text='Points awarded for taking this role.', validators=[django.core.validators.MinValueValidator(0)])),
            ],
        ),
        migrations.CreateModel(
            name='GiftContribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('deadline', models.DateField()),
                ('collection_target', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(choices=[('open', 'Open'), ('closed', 'Closed'), ('canceled', 'Canceled')], default='open', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invitation_sent', models.BooleanField(default=False)),
                ('reminder_sent', models.BooleanField(default=False)),
                ('is_auto_generated', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='GiftProposal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vote_score', models.IntegerField(db_index=True, default=0)),
                ('num_vote_up', models.PositiveIntegerField(db_index=True, default=0)),
                ('num_vote_down', models.PositiveIntegerField(db_index=True, default=0)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('photo', models.ImageField(blank=True, null=True, upload_to='gift_photos/')),
                ('link', models.URLField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GiftSearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=50)),
                ('purpose', models.CharField(max_length=255)),
                ('deadline', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('final_results_sent', models.BooleanField(default=False)),
                ('invitation_sent', models.BooleanField(default=False)),
                ('reminder_sent', models.BooleanField(default=False)),
                ('is_auto_generated', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='RoleConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('organizer', 'Organizer'), ('attendee', 'Attendee'), ('manager', 'Manager'), ('honouree', 'Honouree')], max_length=50, unique=True)),
                ('points', models.IntegerField(default=0, help_text='Points awarded for taking this role.', validators=[django.core.validators.MinValueValidator(0)])),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True, help_text='Additional comments or details about the task.', null=True)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('overdue', 'Overdue'), ('reminder', 'Reminder Sent')], default='pending', help_text='Current status of the task.', max_length=20)),
                ('is_cost_related', models.BooleanField(default=False, help_text='Indicates if this task incurs costs.')),
                ('budget', models.DecimalField(blank=True, decimal_places=2, help_text='Budget allocated for this task.', max_digits=10, null=True)),
                ('actual_expenses', models.DecimalField(blank=True, decimal_places=2, help_text='Actual expenses incurred for this task.', max_digits=10, null=True)),
                ('attachment', models.FileField(blank=True, help_text='Optional attachment, e.g. receipts or planning documents.', null=True, upload_to='task_attachments/')),
                ('base_points', models.IntegerField(default=0, help_text='Base points for completing the task on time.', validators=[django.core.validators.MinValueValidator(0)])),
                ('penalty_points', models.IntegerField(default=0, help_text='Penalty points for late or non-completion of the task.', validators=[django.core.validators.MaxValueValidator(0)])),
                ('points_awarded', models.IntegerField(blank=True, help_text='Final points awarded after completion (may include penalties for overdue tasks).', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='Timestamp when the task was completed.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('base_points', models.IntegerField(default=0, help_text='Default base points for this task template.', validators=[django.core.validators.MinValueValidator(0)])),
                ('penalty_points', models.IntegerField(default=0, help_text='Default penalty points for this task template.', validators=[django.core.validators.MaxValueValidator(0)])),
                ('task_type', models.CharField(choices=[('event', 'Event'), ('gift', 'Gift')], default='event', max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birthday', models.DateField(blank=True, null=True)),
                ('onboarding', models.DateField(blank=True, null=True)),
                ('farewell', models.DateField(blank=True, null=True)),
                ('wedding', models.DateField(blank=True, null=True)),
                ('about_me', models.TextField(blank=True)),
                ('is_inactive', models.BooleanField(default=False)),
                ('total_score', models.IntegerField(default=0)),
                ('task_score', models.IntegerField(default=0)),
                ('role_score', models.IntegerField(default=0)),
                ('gift_score', models.IntegerField(default=0)),
                ('payment_score', models.IntegerField(default=0)),
                ('total_score_past', models.IntegerField(default=0)),
                ('task_score_past', models.IntegerField(default=0)),
                ('role_score_past', models.IntegerField(default=0)),
                ('gift_score_past', models.IntegerField(default=0)),
                ('payment_score_past', models.IntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('type', models.CharField(choices=[('task', 'Task'), ('event', 'Event'), ('gift', 'Gift')], default='event', max_length=20)),
                ('status', models.CharField(choices=[('billed', 'Billed'), ('paid', 'Paid'), ('confirmed', 'Confirmed')], default='billed', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.userprofile')),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.event')),
                ('from_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions_sent', to='event_planner.userprofile')),
                ('gift_contribution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.giftcontribution')),
                ('gift_search', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.giftsearch')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.task')),
                ('to_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions_received', to='event_planner.userprofile')),
            ],
        ),
        migrations.CreateModel(
            name='TaskScoreHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='task', editable=False, max_length=10)),
                ('points_change', models.IntegerField(help_text='Change in points (positive for awards, negative for penalties).')),
                ('score_type', models.CharField(choices=[('task', 'Task'), ('penalty', 'Penalty'), ('other', 'Other')], default='task', help_text='Type of score change.', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True, help_text="Optional note explaining the score change (e.g. 'Completed on time', 'Overdue penalty', etc.)")),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_history', to='event_planner.task')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_history', to='event_planner.userprofile')),
            ],
        ),
        migrations.AddField(
            model_name='task',
            name='assigned_to',
            field=models.ManyToManyField(blank=True, related_name='tasks', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='task',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='event_planner.event'),
        ),
        migrations.AddField(
            model_name='task',
            name='template',
            field=models.ForeignKey(blank=True, help_text='If set, this task was created from a predefined template.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='event_planner.tasktemplate'),
        ),
        migrations.CreateModel(
            name='RoleScoreHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='role', editable=False, max_length=10)),
                ('role', models.CharField(help_text='The role the user took in the event.', max_length=50)),
                ('points_awarded', models.IntegerField(help_text='Points awarded for this role.')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True, help_text='Optional details about the score awarded.')),
                ('event_participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_score_history', to='event_planner.eventparticipant')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_score_history', to='event_planner.userprofile')),
            ],
        ),
        migrations.CreateModel(
            name='PaymentScoreHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='payment', max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('points_awarded', models.IntegerField(help_text='Points awarded for this payment.')),
                ('score_type', models.CharField(choices=[('task', 'Task'), ('event', 'Event'), ('gift', 'Gift')], default='event', help_text='Type of score change.', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True, help_text='Optional details about the score awarded.')),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.event')),
                ('gift_contribution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.giftcontribution')),
                ('gift_search', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.giftsearch')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='event_planner.task')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event_planner.userprofile')),
            ],
        ),
        migrations.AddField(
            model_name='giftsearch',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_searches_created', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='giftsearch',
            name='donee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_searches_received', to='event_planner.userprofile'),
        ),
        migrations.CreateModel(
            name='GiftScoreHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='gift', editable=False, max_length=10)),
                ('points_change', models.IntegerField(help_text='Change in points (positive for awards, negative for penalties).')),
                ('score_type', models.CharField(choices=[('proposal', 'Proposal'), ('vote', 'Vote'), ('winner', 'Winner')], default='proposal', help_text='Type of score change.', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True, help_text="Optional note explaining the score change (e.g. 'Proposed the winning gift', etc.)")),
                ('gift_proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_history', to='event_planner.giftproposal')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_score_history', to='event_planner.userprofile')),
            ],
        ),
        migrations.AddField(
            model_name='giftproposal',
            name='gift_search',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proposals', to='event_planner.giftsearch'),
        ),
        migrations.AddField(
            model_name='giftproposal',
            name='proposed_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_proposals', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='giftcontribution',
            name='donee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_contributions_received', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='giftcontribution',
            name='gift_search',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='event_planner.giftsearch'),
        ),
        migrations.AddField(
            model_name='giftcontribution',
            name='manager',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gift_contributions_managed', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='eventparticipant',
            name='user_profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='event',
            name='participants',
            field=models.ManyToManyField(related_name='events', through='event_planner.EventParticipant', to='event_planner.userprofile'),
        ),
        migrations.AddField(
            model_name='event',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_event', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contributor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contributions', to='event_planner.userprofile')),
                ('gift_contribution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contributions', to='event_planner.giftcontribution')),
            ],
        ),
        migrations.CreateModel(
            name='PastUserScores',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_score', models.IntegerField(default=0)),
                ('task_score', models.IntegerField(default=0)),
                ('role_score', models.IntegerField(default=0)),
                ('gift_score', models.IntegerField(default=0)),
                ('payment_score', models.IntegerField(default=0)),
                ('score_date', models.DateField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'score_date')},
            },
        ),
        migrations.AlterUniqueTogether(
            name='eventparticipant',
            unique_together={('event', 'user_profile', 'role')},
        ),
    ]
