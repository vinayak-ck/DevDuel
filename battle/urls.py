# battle/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('',              views.lobby,         name='lobby'),
    path('create/',       views.create_battle, name='create_battle'),
    path('join/<str:room_id>/', views.join_battle, name='join_battle'),
    path('room/<str:room_id>/', views.battle_room,  name='battle_room'),
    path('api/status/<str:room_id>/', views.battle_status_api, name='battle_status_api'),
]