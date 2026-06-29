from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ApplicationForm, OpportunityForm
from .models import Application, Opportunity


def public_opportunities(request):
	opportunities = Opportunity.objects.filter(is_active=True)
	return render(
		request,
		'opportunities/public_opportunities.html',
		{'opportunities': opportunities},
	)


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
		form = OpportunityForm(request.POST, request.FILES)
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


@login_required
def manage_posted_opportunities(request):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can manage posted opportunities.')
		return redirect('player_dashboard')

	opportunities = (
		Opportunity.objects.filter(scout=request.user)
		.prefetch_related('applications__player')
	)

	return render(
		request,
		'scouts/manage_opportunities.html',
		{'opportunities': opportunities},
	)


@login_required
def delete_posted_opportunity(request, opportunity_id):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can delete posted opportunities.')
		return redirect('player_dashboard')

	if request.method != 'POST':
		return redirect('manage_posted_opportunities')

	opportunity = get_object_or_404(Opportunity, id=opportunity_id, scout=request.user)
	title = opportunity.title

	if opportunity.poster_image:
		opportunity.poster_image.delete(save=False)
	opportunity.delete()

	messages.success(request, f'Opportunity "{title}" deleted successfully.')
	return redirect('manage_posted_opportunities')


@login_required
def update_application_status(request, application_id, status):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can update application status.')
		return redirect('player_dashboard')

	if request.method != 'POST':
		return redirect('manage_posted_opportunities')

	valid_statuses = {'shortlisted', 'rejected', 'pending'}
	if status not in valid_statuses:
		messages.error(request, 'Invalid status update requested.')
		return redirect('manage_posted_opportunities')

	application = get_object_or_404(
		Application.objects.select_related('opportunity', 'player'),
		id=application_id,
		opportunity__scout=request.user,
	)

	application.status = status
	application.save(update_fields=['status'])

	if status == 'shortlisted':
		messages.success(request, f'{application.player.full_name} has been approved (shortlisted).')
	elif status == 'rejected':
		messages.info(request, f'{application.player.full_name} has been rejected.')
	else:
		messages.info(request, f'{application.player.full_name} status reset to pending.')

	return redirect('manage_posted_opportunities')
