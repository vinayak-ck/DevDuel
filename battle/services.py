# battle/services.py
import redis
from channels.db import database_sync_to_async
from .elo import calculate_elo


def process_battle_result_sync(battle_id: int, winner_username: str) -> dict:
    """
    Called after a battle ends (someone got AC).
    Runs synchronously — wrap with database_sync_to_async when calling from consumer.

    1. Fetch battle + both player profiles
    2. Calculate new ELO ratings
    3. Update UserProfile in DB
    4. Save RatingHistory rows for both players
    5. Update Redis leaderboard (Sorted Set)
    6. Return rating change data for the battle-over broadcast
    """
    from django.contrib.auth.models import User
    from .models import Battle, RatingHistory
    from users.models import UserProfile

    battle   = Battle.objects.select_related(
        'player_a', 'player_b', 'problem'
    ).get(id=battle_id)

    player_a = battle.player_a
    player_b = battle.player_b

    if not player_a or not player_b:
        # solo room — no ELO update needed
        return {'error': 'Battle missing a player'}

    # get or create profiles
    profile_a, _ = UserProfile.objects.get_or_create(user=player_a)
    profile_b, _ = UserProfile.objects.get_or_create(user=player_b)

    # determine who is A and B in ELO terms
    winner = 'A' if player_a.username == winner_username else 'B'

    # calculate new ratings
    result = calculate_elo(
        rating_a=profile_a.elo_rating,
        rating_b=profile_b.elo_rating,
        winner=winner,
        battles_a=profile_a.battles_played,
        battles_b=profile_b.battles_played,
    )

    # ── update profile_a ──
    profile_a.elo_rating     = result.player_a_new
    profile_a.battles_played += 1
    if winner == 'A':
        profile_a.wins       += 1
        profile_a.win_streak += 1
    else:
        profile_a.losses     += 1
        profile_a.win_streak  = 0
    if profile_a.battles_played >= 20:
        profile_a.is_provisional = False
    profile_a.save()

    # ── update profile_b ──
    profile_b.elo_rating     = result.player_b_new
    profile_b.battles_played += 1
    if winner == 'B':
        profile_b.wins       += 1
        profile_b.win_streak += 1
    else:
        profile_b.losses     += 1
        profile_b.win_streak  = 0
    if profile_b.battles_played >= 20:
        profile_b.is_provisional = False
    profile_b.save()

    # ── save rating history for player_a ──
    RatingHistory.objects.create(
        player=player_a,
        battle=battle,
        opponent=player_b,
        rating_before=result.player_a_old,
        rating_after=result.player_a_new,
        change=result.player_a_change,
        result='win' if winner == 'A' else 'loss',
    )

    # ── save rating history for player_b ──
    RatingHistory.objects.create(
        player=player_b,
        battle=battle,
        opponent=player_a,
        rating_before=result.player_b_old,
        rating_after=result.player_b_new,
        change=result.player_b_change,
        result='win' if winner == 'B' else 'loss',
    )

    # ── update Redis leaderboard (Sorted Set) ──
    try:
        r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
        r.zadd('devduel:leaderboard', {
            player_a.username: result.player_a_new,
            player_b.username: result.player_b_new,
        })
        print(f"[ELO] {player_a.username}: {result.player_a_old}→{result.player_a_new} "
              f"({'+' if result.player_a_change >= 0 else ''}{result.player_a_change})")
        print(f"[ELO] {player_b.username}: {result.player_b_old}→{result.player_b_new} "
              f"({'+' if result.player_b_change >= 0 else ''}{result.player_b_change})")
    except Exception as e:
        print(f"[ELO] Redis update failed: {e}")

    return {
        'player_a': {
            'username':   player_a.username,
            'old_rating': result.player_a_old,
            'new_rating': result.player_a_new,
            'change':     result.player_a_change,
        },
        'player_b': {
            'username':   player_b.username,
            'old_rating': result.player_b_old,
            'new_rating': result.player_b_new,
            'change':     result.player_b_change,
        },
        'winner': winner_username,
    }


# wrap for async consumer use
process_battle_result = database_sync_to_async(process_battle_result_sync)