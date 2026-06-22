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

            if user.role == 'player':
                return redirect('player_dashboard')

            return redirect('scout_dashboard')

    else:

        form = RegistrationForm()

    return render(
        request,
        'users/register.html',
        {'form': form}
    )


def login_view(request):

    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            user = authenticate(
                request,
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )

            if user:

                login(request, user)

                if user.role == 'player':
                    return redirect('player_dashboard')

                return redirect('scout_dashboard')

    else:

        form = LoginForm()

    return render(
        request,
        'users/login.html',
        {'form': form}
    )