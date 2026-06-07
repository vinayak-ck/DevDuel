# battle/elo.py
from dataclasses import dataclass


@dataclass
class ELOResult:
    player_a_old:      int
    player_b_old:      int
    player_a_new:      int
    player_b_new:      int
    player_a_change:   int
    player_b_change:   int
    player_a_expected: float
    player_b_expected: float


def expected_score(rating_a: int, rating_b: int) -> float:
    """
    Probability that player A beats player B.
    E_A = 1 / (1 + 10^((R_B - R_A) / 400))
    """
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def get_k_factor(rating: int, battles_played: int) -> int:
    """
    Dynamic K-factor:
      K=64 → new players (<20 battles) — finds true level fast
      K=32 → standard players
      K=16 → high-rated (2000+) — stable rating
    """
    if battles_played < 20:
        return 64
    elif rating >= 2000:
        return 16
    return 32


def calculate_elo(
    rating_a:   int,
    rating_b:   int,
    winner:     str,        # 'A' or 'B'
    battles_a:  int = 100,
    battles_b:  int = 100,
) -> ELOResult:
    """
    Calculate new ratings after a battle.

    Example:
        result = calculate_elo(1500, 1800, winner='A')
        result.player_a_change  →  +29  (big upset win)
        result.player_b_change  →  -16
    """
    if winner not in ('A', 'B'):
        raise ValueError(f"winner must be 'A' or 'B', got '{winner}'")

    ea = expected_score(rating_a, rating_b)
    eb = 1 - ea

    sa = 1 if winner == 'A' else 0
    sb = 1 - sa

    ka = get_k_factor(rating_a, battles_a)
    kb = get_k_factor(rating_b, battles_b)

    new_a = round(rating_a + ka * (sa - ea))
    new_b = round(rating_b + kb * (sb - eb))

    # floor at 100 — ratings never go below 100
    new_a = max(100, new_a)
    new_b = max(100, new_b)

    return ELOResult(
        player_a_old=rating_a,
        player_b_old=rating_b,
        player_a_new=new_a,
        player_b_new=new_b,
        player_a_change=new_a - rating_a,
        player_b_change=new_b - rating_b,
        player_a_expected=round(ea, 4),
        player_b_expected=round(eb, 4),
    )