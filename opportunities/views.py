from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ApplicationForm, OpportunityForm
from .models import Application, Opportunity


@login_required
def view_opportunities(request):
	if request.user.role != 'player':
		messages.error(request, 'Only players can view and apply for opportunities.')
		return redirect('scout_dashboard')

	opportunities = Opportunity.objects.filter(is_active=True)
	applied_ids = set(
		Application.objects.filter(player=request.user).values_list('opportunity_id', flat=True)
	)

	return render(
		request,
		'players/viewopportunity.html',
		{
			'opportunities': opportunities,
			'applied_ids': applied_ids,
			'application_form': ApplicationForm(),
		},
	)


@login_required
def apply_opportunity(request, opportunity_id):
	if request.user.role != 'player':
		messages.error(request, 'Only players can apply for opportunities.')
		return redirect('scout_dashboard')

	opportunity = get_object_or_404(Opportunity, id=opportunity_id, is_active=True)

	existing = Application.objects.filter(opportunity=opportunity, player=request.user).exists()
	if existing:
		messages.info(request, 'You already applied for this opportunity.')
		return redirect('view_opportunities')

	form = ApplicationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		Application.objects.create(
			opportunity=opportunity,
			player=request.user,
			motivation=form.cleaned_data['motivation'],
		)
		messages.success(request, 'Application submitted successfully.')
	else:
		messages.error(request, 'Could not submit application. Please try again.')

	return redirect('view_opportunities')


@login_required
def my_applications(request):
	if request.user.role != 'player':
		messages.error(request, 'Only players can view applications.')
		return redirect('scout_dashboard')

	applications = Application.objects.select_related('opportunity').filter(player=request.user)
	return render(
		request,
		'players/applications.html',
		{'applications': applications},
	)


@login_required
def post_opportunity(request):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can post opportunities.')
		return redirect('player_dashboard')

	is_verified = getattr(request.user.scout_profile, 'verified', False)
	if not is_verified:
		messages.warning(request, 'Your scout account is pending verification. Posting is disabled until approved by admin.')

	if request.method == 'POST':
		if not is_verified:
			return redirect('post_opportunity')
		form = OpportunityForm(request.POST)
		if form.is_valid():
			opportunity = form.save(commit=False)
			opportunity.scout = request.user
			opportunity.save()
			messages.success(request, 'Opportunity posted successfully.')
			return redirect('post_opportunity')
	else:
		form = OpportunityForm()

	posted_opportunities = Opportunity.objects.filter(scout=request.user)
	return render(
		request,
		'scouts/postopportunity.html',
		{
			'form': form,
			'posted_opportunities': posted_opportunities,
			'is_verified': is_verified,
		},
	)
