# battle/views.py
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Battle
from problems.models import Problem


@login_required
def lobby(request):
    """
    Shows all open battle rooms (status=waiting).
    Player can join one or create a new one.
    """
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
    """
    Creates a new battle room with a random active problem.
    Redirects player to the room.
    """
    # pick a random active problem
    problems = Problem.objects.filter(is_active=True)
    if not problems.exists():
        return render(request, 'battle/lobby.html', {
            'error': 'No active problems found. Ask admin to add some!',
            'open_battles': [],
        })

    problem = random.choice(list(problems))

    # create the battle
    battle = Battle.objects.create(
        player_a=request.user,
        problem=problem,
        status='waiting',
    )

    return redirect('battle_room', room_id=battle.room_id)


@login_required
def join_battle(request, room_id):
    """
    Player joins an existing waiting room.
    """
    battle = get_object_or_404(Battle, room_id=room_id)

    # can't join a room that's already active or finished
    if battle.status != 'waiting':
        return redirect('lobby')

    # can't join your own room (player_a)
    if battle.player_a == request.user:
        return redirect('battle_room', room_id=room_id)

    return redirect('battle_room', room_id=room_id)


@login_required
def battle_room(request, room_id):
    """
    The battle room page — serves the HTML.
    All real-time logic is handled by WebSocket (BattleConsumer).
    """
    battle = get_object_or_404(
        Battle.objects.select_related('player_a', 'player_b', 'problem'),
        room_id=room_id
    )

    # make sure this user belongs to this battle
    if (battle.player_a != request.user
            and battle.player_b != request.user
            and battle.status == 'waiting'
            and battle.player_a != request.user):
        # redirect non-participants to join
        return redirect('join_battle', room_id=room_id)

    return render(request, 'battle/room.html', {
        'battle':       battle,
        'room_id':      room_id,
        'current_user': request.user.username,
        'problem':      battle.problem,
    })


def battle_status_api(request, room_id):
    """Simple JSON endpoint to check battle status."""
    battle = get_object_or_404(Battle, room_id=room_id)
    return JsonResponse({
        'status':   battle.status,
        'player_a': battle.player_a.username if battle.player_a else None,
        'player_b': battle.player_b.username if battle.player_b else None,
    })