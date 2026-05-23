from django.contrib import admin
from .models import Battle, Submission, RatingHistory


class SubmissionInline(admin.TabularInline):
    model        = Submission
    extra        = 0
    readonly_fields = ['player', 'language', 'verdict',
                       'time_ms', 'test_cases_passed', 'submitted_at']
    can_delete   = False


@admin.register(Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display  = ['room_id', 'player_a', 'player_b',
                     'problem', 'status', 'created_at']
    list_filter   = ['status']
    search_fields = ['room_id', 'player_a__username', 'player_b__username']
    readonly_fields = ['room_id', 'created_at', 'started_at', 'finished_at']
    inlines       = [SubmissionInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display  = ['player', 'battle', 'language',
                     'verdict', 'time_ms', 'submitted_at']
    list_filter   = ['verdict', 'language']
    search_fields = ['player__username']
    readonly_fields = ['submitted_at']


@admin.register(RatingHistory)
class RatingHistoryAdmin(admin.ModelAdmin):
    list_display  = ['player', 'rating_before', 'rating_after',
                     'change', 'result', 'opponent', 'created_at']
    list_filter   = ['result']
    search_fields = ['player__username']
    readonly_fields = ['created_at']