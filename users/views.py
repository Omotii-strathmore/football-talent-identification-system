from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistrationForm


def register_view(request):
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			messages.success(request, 'Account created successfully.')
			if user.role == 'player':
				return redirect('player_page')
			return redirect('scout_page')
	else:
		initial = {}
		role = request.GET.get('role')
		if role in dict(RegistrationForm.base_fields['role'].choices):
			initial['role'] = role
		form = RegistrationForm(initial=initial)

	return render(request, 'register.html', {'form': form})


def login_view(request):
	if request.method == 'POST':
		form = LoginForm(request.POST)
		if form.is_valid():
			user = authenticate(
				request,
				email=form.cleaned_data['email'],
				password=form.cleaned_data['password'],
			)
			if user is not None:
				login(request, user)
				messages.success(request, 'Welcome back.')
				if user.role == 'player':
					return redirect('player_page')
				return redirect('scout_page')
			form.add_error(None, 'Invalid email or password.')
	else:
		form = LoginForm()

	return render(request, 'login.html', {'form': form})


def player_page(request):
	return render(request, 'players/psignin.html')


def scout_page(request):
	return render(request, 'scouts/ssignin.html')
