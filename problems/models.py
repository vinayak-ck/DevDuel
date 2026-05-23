from django.db import models
from django.utils.text import slugify


class Tag(models.Model):
    name  = models.CharField(max_length=50, unique=True)
    slug  = models.SlugField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#6366f1')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Problem(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy',   'Easy'),
        ('medium', 'Medium'),
        ('hard',   'Hard'),
    ]

    slug               = models.SlugField(max_length=100, unique=True)
    title              = models.CharField(max_length=200)
    description        = models.TextField()
    difficulty         = models.CharField(
                             max_length=10,
                             choices=DIFFICULTY_CHOICES,
                             default='medium',
                             db_index=True
                         )
    time_limit_seconds = models.FloatField(default=5.0)
    memory_limit_mb    = models.IntegerField(default=256)
    input_format       = models.TextField(blank=True)
    output_format      = models.TextField(blank=True)
    sample_input       = models.TextField(blank=True)
    sample_output      = models.TextField(blank=True)
    tags               = models.ManyToManyField(
                             Tag, blank=True, related_name='problems'
                         )
    is_active          = models.BooleanField(default=True, db_index=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['difficulty', 'title']

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class TestCase(models.Model):
    problem         = models.ForeignKey(
                          Problem, on_delete=models.CASCADE,
                          related_name='test_cases', db_index=True
                      )
    input_data      = models.TextField()
    expected_output = models.TextField()
    order           = models.IntegerField(default=0)
    is_sample       = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        kind = 'Sample' if self.is_sample else 'Hidden'
        return f"{kind} TC #{self.order} — {self.problem.title}"