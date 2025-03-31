import math
from decimal import Decimal
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, Count
from django.utils import timezone
from event_planner.job_config import JOB_CONFIG
from .models import *
from vote.models import Vote



# -------------------------------------------------------------
# USER
# -------------------------------------------------------------
# Signal handler with post save signal connected with user model
# -------------------------------------------------------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, raw, **kwargs):
    # Create UserProfile object if User object is created (not loaded!)
    #if created and not raw:
    if created:
        UserProfile.objects.get_or_create(user=instance)




# -------------------------------------------------------------
# TOTAL SCORE
# -------------------------------------------------------------
# Signal which updates total_points when UserProfile changes
# -------------------------------------------------------------
@receiver(pre_save, sender=UserProfile)
def update_total_score(sender, instance, **kwargs):
    # Calculate sum of total scores from all scores
    role_score = instance.role_score or 0
    task_score = instance.task_score or 0
    gift_score = instance.gift_score or 0
    payment_score = instance.payment_score or 0
    total = role_score + task_score + gift_score + payment_score
    # Calculate sum of total past scores from all past scores
    role_score_past = instance.role_score_past or 0
    task_score_past = instance.task_score_past or 0
    gift_score_past = instance.gift_score_past or 0
    payment_score_past = instance.payment_score_past or 0
    total_past = role_score_past + task_score_past + gift_score_past + payment_score_past
    # Write calculated points to profile of the user
    instance.total_score = total
    instance.total_score_past = total_past




# -------------------------------------------------------------
# TASK SCORE
# -------------------------------------------------------------
# Signal which updates points_awarded and completed_at when status of task changes
# -------------------------------------------------------------
@receiver(pre_save, sender=Task)
def update__task_score(sender, instance, **kwargs):
    if not instance.pk:
        # If task is new (no primary key!) and status is 'completed'
        if instance.status == 'completed':
            # Award points for task fullfilment
            instance.points_awarded = instance.base_points or 0
            # Set completed_at to now
            instance.completed_at = timezone.now()
        # If task is new (no primary key!) and 'overdue'
        elif instance.due_date and instance.due_date < timezone.now():
            # Assign penalty points
            instance.status = 'overdue'
            instance.points_awarded = instance.penalty_points or 0
    else:
        # If record is not new, retrieve it before value changes
        instance_presave = Task.objects.get(pk=instance.pk)
        # If status is changing from non-completed to completed, update completed_at and points
        if instance_presave.status != 'completed' and instance.status == 'completed':
            instance.points_awarded = (instance_presave.points_awarded or 0) + (instance.base_points or 0)
            instance.completed_at = timezone.now()
        # If status is changing from completed to something else, clear completed_at and remove points
        elif instance_presave.status == 'completed' and instance.status != 'completed':
            instance.points_awarded = (instance_presave.points_awarded or 0) - (instance.base_points or 0)
            instance.completed_at = None
        # If status is changing from non-overdue to overdue, assign penalty points
        # Note: Once task was overdue, penalty cannot be removed
        elif instance_presave.status != 'overdue' and instance.status == 'overdue':
            instance.points_awarded = (instance_presave.points_awarded or 0) + (instance.penalty_points or 0)
        # If task is overdue, change status and deduct penalty points
        elif  instance.due_date and instance.due_date < timezone.now():
            # Assign penalty points
            instance.status = 'overdue'
            instance.points_awarded = instance.penalty_points or 0



# -------------------------------------------------------------
# Signal triggered every time a Task record is created/edited
# -------------------------------------------------------------
@receiver(post_save, sender=Task)
def update_task_score_history(sender, instance, created, **kwargs):
    # Check if task qualifies for a reward
    if instance.status == 'completed':
        # Iterate over each assigned user
        for user_profile in instance.assigned_to.all():
            # Create award record
            history, was_created = TaskScoreHistory.objects.get_or_create(
                task=instance,
                user_profile=user_profile,
                score_type='task',
                defaults={
                    'points_change': instance.base_points,
                    'note': f"Points awarded for task '{instance.title}' in event '{instance.event}'."
                }
            )
            # If a record exists and base_points have changed, update it
            if not was_created and history.points_change != instance.base_points:
                history.points_change = instance.base_points
                history.save()

    # Check if task qualifies for a penalty
    elif instance.status == 'overdue':
        # Iterate over each assigned user
        for user_profile in instance.assigned_to.all():
            # Create penalty record
            history, was_created = TaskScoreHistory.objects.get_or_create(
                task=instance,
                user_profile=user_profile,
                score_type='penalty',
                defaults={
                    'points_change': instance.penalty_points,
                    'note': f"Points deducted for late task '{instance.title}' in event '{instance.event}'."
                }
            )
            # If a record already exists, update it
            if not was_created and history.points_change != instance.penalty_points:
                history.points_change = instance.penalty_points
                history.save()

    # If points awarded without qualification, remove history and completed_at
    # Note: Once a task was overdue, penalty cannot be removed
    else:
        # Iterate over each assigned user
        for user_profile in instance.assigned_to.all():
            # Look for records (award only) to be removed
            history = TaskScoreHistory.objects.filter(
                task=instance,
                user_profile=user_profile,
                score_type='task')
            if history.exists():
                history.delete()



# -------------------------------------------------------------
# Helper function to calculate the task score of a user by summing up all point changes from TaskScoreHistory
# -------------------------------------------------------------
def update_task_score(user_profile):
    # Calculate the sum of all points_change values for the given user profile
    aggregate = TaskScoreHistory.objects.filter(user_profile=user_profile).aggregate(total=Sum('points_change'))
    total = aggregate['total'] if aggregate['total'] is not None else 0
    # Save calculated points to profile of the user
    user_profile.task_score = total
    user_profile.save(update_fields=['task_score', 'total_score', 'total_score_past'])



# -------------------------------------------------------------
# Signal triggered every time a TaskScoreHistory record is saved 
# -------------------------------------------------------------
@receiver(post_save, sender=TaskScoreHistory)
def update_task_score_on_save(sender, instance, created, **kwargs):
    # Recalculate the task score
    update_task_score(instance.user_profile)



# -------------------------------------------------------------
# Signal triggered every time a TaskScoreHistory record is deleted 
# -------------------------------------------------------------
@receiver(post_delete, sender=TaskScoreHistory)
def update_task_score_on_delete(sender, instance, **kwargs):
    # Recalculate the task score
    update_task_score(instance.user_profile)




# -------------------------------------------------------------
# ROLE SCORE
# -------------------------------------------------------------
# Signal triggered every time a EventParticipant record is created 
# -------------------------------------------------------------
@receiver(post_save, sender=EventParticipant)
def update_role_score_history(sender, instance, created, **kwargs):
    if created:
        # Retrieve points for role from RoleConfiguration model
        config = RoleConfiguration.objects.filter(role=instance.role).first()
        points = config.points if config else 0
        
        # Create history record for this role assignment
        RoleScoreHistory.objects.create(
            event_participant=instance,
            user_profile=instance.user_profile,
            role=instance.role,
            points_awarded=points,
            note=f"Points awarded for role '{instance.role}' in event '{instance.event}'."
        )



# -------------------------------------------------------------
# Helper function to calculate the role score of a user by summing up all point changes from RoleScoreHistory
# -------------------------------------------------------------
def update_role_score(user_profile):
    # Calculate the sum of all points_awarded values for the given user profile
    aggregate = RoleScoreHistory.objects.filter(user_profile=user_profile).aggregate(total=Sum('points_awarded'))
    total = aggregate['total'] if aggregate['total'] is not None else 0
    # Save calculated points to profile of the user
    user_profile.role_score = total
    user_profile.save(update_fields=['role_score', 'total_score', 'total_score_past'])



# -------------------------------------------------------------
# Signal triggered every time a RoleScoreHistory record is saved 
# -------------------------------------------------------------
@receiver(post_save, sender=RoleScoreHistory)
def update_role_score_on_save(sender, instance, created, **kwargs):
    # Recalculate the role score
    update_role_score(instance.user_profile)



# -------------------------------------------------------------
# Signal triggered every time a RoleScoreHistory record is deleted 
# -------------------------------------------------------------
@receiver(post_delete, sender=RoleScoreHistory)
def update_role_score_on_delete(sender, instance, **kwargs):
    # Recalculate the role score
    update_role_score(instance.user_profile)



# -------------------------------------------------------------
# GIFT SCORE
# -------------------------------------------------------------
# Signal triggered every time a Gift vote is created/edited
# -------------------------------------------------------------
@receiver(post_save, sender=Vote)
def update_gift_score_history_on_vote(sender, instance, created, **kwargs):
    # Retrieve points for role from GiftConfiguration model
    config = GiftConfiguration.objects.filter(role='voter').first()
    points = config.points if config else 0
    user_profile = UserProfile.objects.get(user_id=instance.user_id)
    gift_proposal = GiftProposal.objects.get(id=instance.object_id)

    # Create award record
    history, was_created = GiftScoreHistory.objects.get_or_create(
        type='gift',
        user_profile=user_profile,
        gift_proposal=gift_proposal,
        score_type='vote',
        defaults={
            'points_change': points,
            'note': f"Points awarded for voting on gift '{gift_proposal.title}' in search '{gift_proposal.gift_search.title}'."
        }
    )
    # If a record exists and points have changed, update it
    if not was_created and history.points_change != points:
        history.points_change = points
        history.save()



# -------------------------------------------------------------
# Signal triggered every time a Gift Search has ended or been processed
# -------------------------------------------------------------
@receiver(pre_save, sender=GiftSearch)
def update_gift_score_history_on_winner(sender, instance, **kwargs):
    if instance.pk and instance.final_results_sent == True:
        # If record is not new, retrieve it before value changes
        instance_presave = GiftSearch.objects.get(pk=instance.pk)
        # If status is changing from non-completed to completed, award points
        if instance_presave.final_results_sent == False and instance.final_results_sent == True:
            # Retrieve points for role from GiftConfiguration model
            config = GiftConfiguration.objects.filter(role='winner').first()
            points = config.points if config else 0

            # Retrieve proposal with maximum points
            gs_query = GiftProposal.objects.filter(gift_search=instance)
            if gs_query.exists():
                proposals = list(gs_query)
                # Sort the list 
                sorted_proposals = sorted(proposals, key=lambda proposal: proposal.votes.count(), reverse=True)
                winner_proposal = sorted_proposals[0]
                user_profile = winner_proposal.proposed_by

                # Create history record for this role
                GiftScoreHistory.objects.create(
                    type='gift',
                    user_profile=user_profile,
                    gift_proposal=winner_proposal,
                    score_type='winner',
                    points_change=points,
                    note=f"Points awarded for proposal of gift '{winner_proposal.title}' in search '{instance.title}'."
                )

    elif instance.pk and instance.final_results_sent == False:
        # If record is not new, retrieve it before value changes
        instance_presave = GiftSearch.objects.get(pk=instance.pk)
        # If status is changing from completed to non-completed, remove points
        if instance_presave.final_results_sent == True and instance.final_results_sent == False:
            # Retrieve all proposals
            proposals = GiftProposal.objects.filter(gift_search=instance)
            for proposal in proposals:
                history = GiftScoreHistory.objects.filter(
                    type='gift',
                    gift_proposal=proposal,
                    score_type='winner',               
                )

                if history.exists():
                    history.delete()     
                          


# -------------------------------------------------------------
# Signal triggered every time a Gift vote is created/edited
# -------------------------------------------------------------
@receiver(post_save, sender=GiftProposal)
def update_gift_score_history_on_proposal(sender, instance, created, **kwargs):
    if created:
        # Retrieve points for role from GiftConfiguration model
        config = GiftConfiguration.objects.filter(role='proposer').first()
        points = config.points if config else 0

        # Create history record for this role
        GiftScoreHistory.objects.create(
            type='gift',
            user_profile=instance.proposed_by,
            gift_proposal=instance,
            score_type='proposal',
            points_change=points,
            note=f"Points awarded for proposal of gift '{instance.title}' in search '{instance.gift_search.title}'."
        )



# -------------------------------------------------------------
# Signal triggered every time a Gift contribution is closed/canceled
# -------------------------------------------------------------
@receiver(post_save, sender=GiftContribution)
def update_transactions_from_gift_contribution(sender, instance, **kwargs):
    # Use gift_contribution field to link transactions
    if instance.status == "closed":
        # Remove any existing transactions for this gift search (if available)
        if instance.gift_search:
            Transaction.objects.filter(gift_contribution=instance, type="gift").delete()
        # For each contribution, create a corresponding transaction
        for contribution in instance.contributions.all():
            if contribution.contributor == instance.manager:
                status = "confirmed"
            else:
                status = "billed"

            Transaction.objects.create(
                from_user=contribution.contributor,
                to_user=instance.manager,
                amount=contribution.value,
                type="gift",
                status=status,
                gift_contribution=instance,
                gift_search=instance.gift_search,
            )

    elif instance.status == "canceled":
        # If status is "canceled", remove any existing Contributions and Transactions for this gift contribution
        Contribution.objects.filter(gift_contribution=instance).delete()
        Transaction.objects.filter(gift_contribution=instance, type="gift").delete()
    elif instance.status == "open":
        # If status is "open", remove any existing Transactions for this gift contribution (existing contributions kept)
        Transaction.objects.filter(gift_contribution=instance, type="gift").delete()


# -------------------------------------------------------------
# Helper function to calculate the gift score of a user by summing up all point changes from GiftScoreHistory
# -------------------------------------------------------------
def update_gift_score(user_profile):
    # Calculate the sum of all points_change values for the given user profile
    aggregate = GiftScoreHistory.objects.filter(user_profile=user_profile).aggregate(total=Sum('points_change'))
    total = aggregate['total'] if aggregate['total'] is not None else 0
    # Save calculated points to profile of the user
    user_profile.gift_score = total
    user_profile.save(update_fields=['gift_score', 'total_score', 'total_score_past'])



# -------------------------------------------------------------
# Signal triggered every time a GiftScoreHistory record is saved 
# -------------------------------------------------------------
@receiver(post_save, sender=GiftScoreHistory)
def update_gift_score_on_save(sender, instance, created, **kwargs):
    # Recalculate the gift score
    update_gift_score(instance.user_profile)



# -------------------------------------------------------------
# Signal triggered every time a GiftScoreHistory record is deleted 
# -------------------------------------------------------------
@receiver(post_delete, sender=GiftScoreHistory)
def update_gift_score_on_delete(sender, instance, **kwargs):
    # Recalculate the gift score
    update_gift_score(instance.user_profile)




# -------------------------------------------------------------
# PAYMENT SCORE
# -------------------------------------------------------------
# Signal triggered when Transaction changes
# -------------------------------------------------------------
@receiver(pre_save, sender=Transaction)
def capture_old_transaction_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Transaction.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Transaction.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None



# -------------------------------------------------------------        
# Signal triggered every time a Payment is created/edited
# -------------------------------------------------------------
@receiver(post_save, sender=Transaction)
def update_payment_score_history_on_payment(sender, instance, created, **kwargs):
    if instance.status == 'confirmed':
        # Retrieve conversion rate for payments from general settings
        config_general = JOB_CONFIG['general']
        conversion_rate = config_general.get('conversion_rate', 0.5)
        payment = instance.amount if instance.amount else 0
        points = math.ceil(Decimal(payment) * Decimal(conversion_rate))

        # Create history record
        if instance.type == 'task':
            history, was_created = PaymentScoreHistory.objects.get_or_create(
                task=instance.task,
                user_profile=instance.from_user,
                amount=payment,
                points_awarded=points,
                score_type='task',
                note=f"Points awarded for task '{instance.title}' in event '{instance.event.title}'."

            )

        if instance.type == 'event':
            history, was_created = PaymentScoreHistory.objects.get_or_create(
                event=instance.event,
                user_profile=instance.from_user,
                amount=payment,
                points_awarded=points,
                score_type='event',
                note=f"Points awarded for event '{instance.event.title}'."

            )

        if instance.type == 'gift':
            history, was_created = PaymentScoreHistory.objects.get_or_create(
                gift_contribution=instance.gift_contribution,
                user_profile=instance.from_user,
                amount=payment,
                points_awarded=points,
                score_type='gift',
                note=f"Points awarded for gift '{instance.gift_contribution}'."

            )
    else:
        # For any status other than 'confirmed', remove any related PaymentScoreHistory records
        if instance.type == 'task':
            PaymentScoreHistory.objects.filter(
                task=instance.task,
                user_profile=instance.from_user,
                type='payment',
                score_type='task'
            ).delete()
        elif instance.type == 'event':
            PaymentScoreHistory.objects.filter(
                event=instance.event,
                user_profile=instance.from_user,
                type='payment',
                score_type='event'
            ).delete()
        elif instance.type == 'gift':
            PaymentScoreHistory.objects.filter(
                gift_contribution=instance.gift_contribution,
                user_profile=instance.from_user,
                type='payment',
                score_type='gift'
            ).delete()

        # If status changes from "billed" to "paid", check overdue status
        # Only process updates and only if old status is available
        old_status = getattr(instance, '_old_status', None)
        if not created and old_status == "billed" and instance.status == "paid":
            # Get overdue threshold (in days)
            overdue_threshold = JOB_CONFIG.get('check_payment_reminder', {}).get('overdue_threshold', 7)
            today = timezone.now().date()
            created_date = instance.created_at.date()
            overdue_days = (today - created_date).days

            if overdue_days >= overdue_threshold:
            #if 10 >= overdue_threshold:
                # Get penalty amount
                payment_penalty = JOB_CONFIG.get('general', {}).get('payment_penalty', -25)
                # Depending on transaction type, create PaymentScoreHistory record with score_type 'penalty'
                if instance.type == 'task':
                    PaymentScoreHistory.objects.create(
                        task=instance.task,
                        user_profile=instance.from_user,
                        amount=instance.amount,
                        points_awarded=payment_penalty,
                        type='penalty',
                        score_type='task',
                        note=f"overdue by {overdue_days} days."
                    )
                elif instance.type == 'event':
                    PaymentScoreHistory.objects.create(
                        event=instance.event,
                        user_profile=instance.from_user,
                        amount=instance.amount,
                        points_awarded=payment_penalty,
                        type='penalty',
                        score_type='event',
                        note=f"overdue by {overdue_days} days."
                    )
                elif instance.type == 'gift':
                    PaymentScoreHistory.objects.create(
                        gift_contribution=instance.gift_contribution,
                        user_profile=instance.from_user,
                        amount=instance.amount,
                        points_awarded=payment_penalty,
                        type='penalty',
                        score_type='gift',
                        note=f"overdue by {overdue_days} days."
                    )



# -------------------------------------------------------------
# Signal triggered every time a Payment is deleted
# -------------------------------------------------------------
@receiver(post_delete, sender=Transaction)
def delete_payment_score_history_on_payment_delete(sender, instance, **kwargs):
    if instance.type == 'task':
        PaymentScoreHistory.objects.filter(
            task=instance.task,
            user_profile=instance.from_user,
            score_type='task'
        ).delete()
    elif instance.type == 'event':
        PaymentScoreHistory.objects.filter(
            event=instance.event,
            user_profile=instance.from_user,
            score_type='event'
        ).delete()
    elif instance.type == 'gift':
        PaymentScoreHistory.objects.filter(
            gift_contribution=instance.gift_contribution,
            user_profile=instance.from_user,
            score_type='gift'
        ).delete()



# -------------------------------------------------------------
# Helper function to calculate the payment score of a user by summing up all point changes from PaymentScoreHistory
# -------------------------------------------------------------
def update_payment_score(user_profile):
    # Calculate the sum of all points_awarded values for the given user profile
    aggregate = PaymentScoreHistory.objects.filter(user_profile=user_profile).aggregate(total=Sum('points_awarded'))
    total = aggregate['total'] if aggregate['total'] is not None else 0
    # Save calculated points to profile of the user
    user_profile.payment_score = total
    user_profile.save(update_fields=['payment_score', 'total_score', 'total_score_past'])



# -------------------------------------------------------------
# Signal triggered every time a PaymentScoreHistory record is saved 
# -------------------------------------------------------------
@receiver(post_save, sender=PaymentScoreHistory)
def update_payment_score_on_save(sender, instance, created, **kwargs):
    # Recalculate the payment score
    update_payment_score(instance.user_profile)



# -------------------------------------------------------------
# Signal triggered every time a PaymentScoreHistory record is deleted 
# -------------------------------------------------------------
@receiver(post_delete, sender=PaymentScoreHistory)
def update_payment_score_on_delete(sender, instance, **kwargs):
    # Recalculate the payment score
    update_payment_score(instance.user_profile)








