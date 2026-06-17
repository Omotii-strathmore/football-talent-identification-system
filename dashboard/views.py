from django.shortcuts import render


def home(request):
	# Simple overview page for players and scouts.
	return render(request, 'home.html')


def opportunities(request):
	# Trials and tournaments page that reuses opp.html.
	return render(request, 'opp.html')
