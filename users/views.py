from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import RegistrationForm, LoginForm


def home(request):
    return render(request, 'users/home.html')


def register_view(request):

    if request.method == 'POST':

        form = RegistrationForm(request.POST)

        if form.is_valid():

            user = form.save()

            login(request, user)

            messages.success(
                request,
                'Account created successfully.'
            )

            if user.role == 'player':
                return redirect('player_page')

            elif user.role == 'scout':
                return redirect('scout_page')

    else:

        form = RegistrationForm()

    return render(
        request,
        'users/register.html',
        {
            'form': form
        }
    )


def login_view(request):

    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = authenticate(
                request,
                email=email,
                password=password
            )

            if user is not None:

                login(request, user)

                messages.success(
                    request,
                    f'Welcome back {user.full_name}'
                )

                if user.role == 'player':
                    return redirect('player_page')

                elif user.role == 'scout':
                    return redirect('scout_page')

            else:

                messages.error(
                    request,
                    'Invalid email or password.'
                )

    else:

        form = LoginForm()

    return render(
        request,
        'users/login.html',
        {
            'form': form
        }
    )

