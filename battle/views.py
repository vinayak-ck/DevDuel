# battle/views.py
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Battle
from problems.models import Problem


@login_required
def lobby(request):
    open_battles = Battle.objects.filter(
        status='waiting'
    ).select_related(
        'player_a', 'problem'
    ).order_by('-created_at')[:20]

    return render(request, 'battle/lobby.html', {
        'open_battles': open_battles,
    })


@login_required
def create_battle(request):
    problems = Problem.objects.filter(is_active=True)
    if not problems.exists():
        return render(request, 'battle/lobby.html', {
            'error': 'No active problems found. Ask admin to add some!',
            'open_battles': [],
        })

    problem = random.choice(list(problems))
    battle  = Battle.objects.create(
        player_a=request.user,
        problem=problem,
        status='waiting',
    )
    return redirect('battle_room', room_id=battle.room_id)


@login_required
def join_battle(request, room_id):
    """
    Just validates the room exists and is joinable,
    then sends the player to the room page.
    The WebSocket consumer handles actually making them player_b.
    """
    battle = get_object_or_404(Battle, room_id=room_id)

    if battle.status in ('finished', 'abandoned'):
        return redirect('lobby')

    # Don't redirect — just go straight to the room
    return redirect('battle_room', room_id=room_id)


@login_required
def battle_room(request, room_id):
    """
    Serves the battle room HTML page.
    ALL game logic (joining, starting, submitting) is handled
    by the WebSocket consumer — not here.
    This view just serves the HTML shell.
    """
    battle = get_object_or_404(
        Battle.objects.select_related('player_a', 'player_b', 'problem'),
        room_id=room_id
    )

    # Only block access if the battle is already over
    # AND this user wasn't part of it
    if (battle.status in ('finished', 'abandoned')
            and battle.player_a != request.user
            and battle.player_b != request.user):
        return redirect('lobby')

    # Everyone else — player_a, player_b, or a new joiner
    # of a waiting room — gets the page.
    # The WebSocket consumer assigns player_b on connect.
    return render(request, 'battle/room.html', {
        'battle':       battle,
        'room_id':      room_id,
        'current_user': request.user.username,
        'problem':      battle.problem,
    })


def battle_status_api(request, room_id):
    battle = get_object_or_404(Battle, room_id=room_id)
    return JsonResponse({
        'status':   battle.status,
        'player_a': battle.player_a.username if battle.player_a else None,
        'player_b': battle.player_b.username if battle.player_b else None,
    })