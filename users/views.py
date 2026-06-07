# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserProfile


def login_view(request):
    if request.user.is_authenticated:
        return redirect('lobby')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/battle/'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'users/login.html', {
        'next': request.GET.get('next', '/battle/')
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('lobby')

    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # validation
        if not username or not password1:
            messages.error(request, 'Username and password are required.')
        elif len(username) < 3:
            messages.error(request, 'Username must be at least 3 characters.')
        elif len(password1) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        elif password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
        else:
            # create user — signal auto-creates UserProfile
            user = User.objects.create_user(
                username=username,
                password=password1,
            )
            login(request, user)
            messages.success(request, f'Welcome to DevDuel, {username}!')
            return redirect('lobby')

    return render(request, 'users/register.html')


def logout_view(request):
    logout(request)
    return redirect('login')