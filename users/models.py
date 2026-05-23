from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user           = models.OneToOneField(
                         User, on_delete=models.CASCADE,
                         related_name='profile'
                     )
    elo_rating     = models.IntegerField(default=1500, db_index=True)
    battles_played = models.IntegerField(default=0)
    wins           = models.IntegerField(default=0)
    losses         = models.IntegerField(default=0)
    win_streak     = models.IntegerField(default=0)
    is_provisional = models.BooleanField(default=True)
    avatar_url     = models.URLField(blank=True, default='')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['-elo_rating']),
        ]

    def __str__(self):
        return f"{self.user.username} — ELO {self.elo_rating}"

    @property
    def win_rate(self):
        total = self.wins + self.losses
        return round(self.wins / total * 100, 1) if total > 0 else 0.0

    @property
    def k_factor(self):
        if self.battles_played < 20:
            return 64
        elif self.elo_rating >= 2000:
            return 16
        return 32

    def update_after_win(self):
        self.wins          += 1
        self.battles_played += 1
        self.win_streak    += 1
        if self.battles_played >= 20:
            self.is_provisional = False
        self.save()

    def update_after_loss(self):
        self.losses        += 1
        self.battles_played += 1
        self.win_streak    = 0
        if self.battles_played >= 20:
            self.is_provisional = False
        self.save()