from django.contrib import admin
from .models import *
from vote.models import Vote
from .forms import EventParticipantForm


admin.site.register(UserProfile)
admin.site.register(PastUserScores)
admin.site.register(Event)
admin.register(EventParticipant)
admin.site.register(GiftConfiguration)
admin.site.register(GiftSearch)
admin.site.register(GiftProposal)
admin.site.register(GiftContribution)
admin.site.register(Contribution)
admin.site.register(RoleConfiguration)
admin.site.register(RoleScoreHistory)
admin.site.register(TaskTemplate)
admin.site.register(Task)
admin.site.register(TaskScoreHistory)
admin.site.register(GiftScoreHistory)
admin.site.register(PaymentScoreHistory)
admin.site.register(Transaction)
admin.site.register(Vote)


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    form = EventParticipantForm