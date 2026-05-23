import uuid
from django.db import models
from django.contrib.auth.models import User


def generate_room_id():
    return f"room-{uuid.uuid4().hex[:8]}"


class Battle(models.Model):
    STATUS_CHOICES = [
        ('waiting',   'Waiting for opponent'),
        ('active',    'In progress'),
        ('finished',  'Finished'),
        ('abandoned', 'Abandoned'),
    ]

    room_id            = models.CharField(
                             max_length=20, unique=True,
                             default=generate_room_id, db_index=True
                         )
    player_a           = models.ForeignKey(
                             User, on_delete=models.SET_NULL,
                             null=True, related_name='battles_as_a'
                         )
    player_b           = models.ForeignKey(
                             User, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='battles_as_b'
                         )
    problem            = models.ForeignKey(
                             'problems.Problem', on_delete=models.SET_NULL,
                             null=True, related_name='battles'
                         )
    winner             = models.ForeignKey(
                             User, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='battles_won'
                         )
    status             = models.CharField(
                             max_length=20, choices=STATUS_CHOICES,
                             default='waiting', db_index=True
                         )
    time_limit_minutes = models.IntegerField(default=30)
    created_at         = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at         = models.DateTimeField(null=True, blank=True)
    finished_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        a = self.player_a.username if self.player_a else 'Anonymous'
        b = self.player_b.username if self.player_b else 'Waiting...'
        return f"{a} vs {b} [{self.status}]"


class Submission(models.Model):
    VERDICT_CHOICES = [
        ('AC',  'Accepted'),
        ('WA',  'Wrong Answer'),
        ('TLE', 'Time Limit Exceeded'),
        ('RE',  'Runtime Error'),
        ('CE',  'Compile Error'),
    ]
    LANGUAGE_CHOICES = [
        ('python', 'Python 3'),
        ('cpp',    'C++ 17'),
        ('java',   'Java 17'),
    ]

    battle            = models.ForeignKey(
                            Battle, on_delete=models.CASCADE,
                            related_name='submissions', db_index=True
                        )
    player            = models.ForeignKey(
                            User, on_delete=models.SET_NULL,
                            null=True, related_name='submissions', db_index=True
                        )
    code              = models.TextField()
    language          = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    verdict           = models.CharField(
                            max_length=5, choices=VERDICT_CHOICES,
                            null=True, blank=True, db_index=True
                        )
    time_ms           = models.FloatField(null=True, blank=True)
    memory_mb         = models.FloatField(null=True, blank=True)
    test_cases_passed = models.IntegerField(default=0)
    total_test_cases  = models.IntegerField(default=0)
    stderr            = models.TextField(blank=True, default='')
    submitted_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        player = self.player.username if self.player else 'Anonymous'
        return f"{player} — {self.verdict or 'pending'} ({self.language})"


class RatingHistory(models.Model):
    RESULT_CHOICES = [
        ('win',       'Win'),
        ('loss',      'Loss'),
        ('abandoned', 'Abandoned'),
    ]

    player        = models.ForeignKey(
                        User, on_delete=models.CASCADE,
                        related_name='rating_history', db_index=True
                    )
    battle        = models.ForeignKey(
                        Battle, on_delete=models.SET_NULL,
                        null=True, related_name='rating_changes'
                    )
    opponent      = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True, related_name='opponent_history'
                    )
    rating_before = models.IntegerField()
    rating_after  = models.IntegerField()
    change        = models.IntegerField()
    result        = models.CharField(max_length=10, choices=RESULT_CHOICES)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.change >= 0 else ''
        return f"{self.player.username}: {self.rating_before} → {self.rating_after} ({sign}{self.change})"