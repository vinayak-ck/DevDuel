# battle/views.py
from pyexpat.errors import messages
import random
import redis as redis_client
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Battle, Submission, RatingHistory
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

import redis as redis_client

def leaderboard(request):
    """
    Top 50 players from Redis Sorted Set.
    Falls back to MySQL if Redis is empty.
    """
    from users.models import UserProfile

    players = []

    try:
        r = redis_client.Redis(host='127.0.0.1', port=6379, decode_responses=True)
        # ZRANGE with REV=True → highest rating first
        entries = r.zrange('devduel:leaderboard', 0, 49, rev=True, withscores=True)

        if entries:
            for rank, (username, score) in enumerate(entries, start=1):
                try:
                    from django.contrib.auth.models import User
                    user    = User.objects.get(username=username)
                    profile = UserProfile.objects.get(user=user)
                    players.append({
                        'rank':           rank,
                        'username':       username,
                        'rating':         int(score),
                        'wins':           profile.wins,
                        'losses':         profile.losses,
                        'battles_played': profile.battles_played,
                        'win_rate':       profile.win_rate,
                        'is_provisional': profile.is_provisional,
                    })
                except Exception:
                    players.append({
                        'rank': rank, 'username': username,
                        'rating': int(score), 'wins': 0,
                        'losses': 0, 'battles_played': 0,
                        'win_rate': 0, 'is_provisional': False,
                    })
    except Exception as e:
        print(f"[Leaderboard] Redis error: {e}")

    # fallback to MySQL if Redis empty
    if not players:
        profiles = UserProfile.objects.select_related('user')\
            .order_by('-elo_rating')[:50]
        for rank, p in enumerate(profiles, start=1):
            players.append({
                'rank':           rank,
                'username':       p.user.username,
                'rating':         p.elo_rating,
                'wins':           p.wins,
                'losses':         p.losses,
                'battles_played': p.battles_played,
                'win_rate':       p.win_rate,
                'is_provisional': p.is_provisional,
            })

    return render(request, 'battle/leaderboard.html', {
        'players':      players,
        'current_user': request.user.username if request.user.is_authenticated else None,
    })


@login_required
def profile(request, username=None):
    """User profile with rating history and battle stats."""
    from django.contrib.auth.models import User
    from users.models import UserProfile

    if username:
        target_user = get_object_or_404(User, username=username)
    else:
        target_user = request.user

    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    # last 20 rating history entries
    history = RatingHistory.objects.filter(
        player=target_user
    ).select_related('opponent', 'battle').order_by('-created_at')[:20]

    # last 10 battles
    from django.db.models import Q
    battles = Battle.objects.filter(
        Q(player_a=target_user) | Q(player_b=target_user)
    ).select_related(
        'player_a', 'player_b', 'problem', 'winner'
    ).order_by('-created_at')[:10]

    # rating chart data (chronological)
    chart_data = list(
        RatingHistory.objects.filter(player=target_user)
        .order_by('created_at')
        .values('rating_after', 'created_at', 'result')[:50]
    )

    return render(request, 'battle/profile.html', {
        'profile':     profile,
        'target_user': target_user,
        'history':     history,
        'battles':     battles,
        'chart_data':  chart_data,
        'is_own':      target_user == request.user,
    })

@login_required
def find_opponent(request):
    """
    Smart matchmaking:
    1. Look for a waiting room where opponent has similar ELO (±300)
    2. If found → join that room
    3. If not found → create a new room and wait
    """
    from users.models import UserProfile
    from django.utils import timezone
    from datetime import timedelta

    # first: clean up rooms older than 10 minutes that are still waiting
    stale_time = timezone.now() - timedelta(minutes=10)
    Battle.objects.filter(
        status='waiting',
        created_at__lt=stale_time
    ).update(status='abandoned')

    # get this player's rating
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    my_rating  = profile.elo_rating
    margin     = 300  # ±300 ELO is a fair match

    # find a waiting room — not created by me, within rating range
    waiting = Battle.objects.filter(
        status='waiting'
    ).exclude(
        player_a=request.user
    ).select_related('player_a', 'player_a__profile').order_by('-created_at')

    # filter by rating proximity
    best_match = None
    for battle in waiting:
        if battle.player_a and hasattr(battle.player_a, 'profile'):
            diff = abs(battle.player_a.profile.elo_rating - my_rating)
            if diff <= margin:
                best_match = battle
                break

    # if no close match, take any waiting room
    if not best_match and waiting.exists():
        best_match = waiting.first()

    if best_match:
        # join this room
        return redirect('battle_room', room_id=best_match.room_id)

    # no waiting room — create a new one
    problems = Problem.objects.filter(is_active=True)
    if not problems.exists():
        messages.error(request, 'No active problems available. Ask admin to add some.')
        return redirect('lobby')

    problem = random.choice(list(problems))
    battle  = Battle.objects.create(
        player_a=request.user,
        problem=problem,
        status='waiting',
    )
    return redirect('battle_room', room_id=battle.room_id)