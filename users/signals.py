from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    # fires every time a User is saved
    # if it's a NEW user, create their profile automatically
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    # if the User already has a profile, save it too
    if hasattr(instance, 'profile'):
        instance.profile.save()