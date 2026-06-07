# battle/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.lobby,          name='lobby'),
    path('create/',                   views.create_battle,  name='create_battle'),
    path('join/<str:room_id>/',       views.join_battle,    name='join_battle'),
    path('room/<str:room_id>/',       views.battle_room,    name='battle_room'),
    path('leaderboard/',              views.leaderboard,    name='leaderboard'),
    path('profile/',                  views.profile,        name='my_profile'),
    path('profile/<str:username>/',   views.profile,        name='user_profile'),
    path('api/status/<str:room_id>/', views.battle_status_api, name='battle_status_api'),
]