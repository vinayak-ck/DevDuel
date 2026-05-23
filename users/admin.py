from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'elo_rating', 'battles_played',
                     'wins', 'losses', 'is_provisional', 'created_at']
    list_filter   = ['is_provisional']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
    ordering      = ['-elo_rating']