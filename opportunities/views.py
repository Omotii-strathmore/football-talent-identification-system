from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ApplicationForm, OpportunityForm
from .models import Application, Opportunity


def _auto_expire_passed_deadline_opportunities():
	today = timezone.localdate()
	Opportunity.objects.filter(is_active=True, deadline__lt=today).update(is_active=False)


def public_opportunities(request):
	_auto_expire_passed_deadline_opportunities()
	selected_view = request.GET.get('view', 'available').strip().lower()
	if selected_view not in {'available', 'history'}:
		selected_view = 'available'

	available_opportunities = Opportunity.objects.filter(is_active=True).order_by('deadline', '-created_at')
	history_opportunities = Opportunity.objects.filter(is_active=False).order_by('-updated_at', '-created_at')
	return render(
		request,
		'opportunities/public_opportunities.html',
		{
			'available_opportunities': available_opportunities,
			'history_opportunities': history_opportunities,
			'selected_view': selected_view,
		},
	)


@login_required
def view_opportunities(request):
	if request.user.role != 'player':
		messages.error(request, 'Only players can view and apply for opportunities.')
		return redirect('scout_dashboard')

	_auto_expire_passed_deadline_opportunities()
	selected_view = request.GET.get('view', 'available').strip().lower()
	if selected_view not in {'available', 'history'}:
		selected_view = 'available'
	today = timezone.localdate()
	available_opportunities = Opportunity.objects.filter(is_active=True).order_by('deadline', '-created_at')
	history_opportunities = Opportunity.objects.filter(is_active=False).order_by('-updated_at', '-created_at')
	applied_ids = set(
		Application.objects.filter(player=request.user).values_list('opportunity_id', flat=True)
	)

	return render(
		request,
		'players/viewopportunity.html',
		{
			'available_opportunities': available_opportunities,
			'history_opportunities': history_opportunities,
			'selected_view': selected_view,
			'applied_ids': applied_ids,
			'application_form': ApplicationForm(),
			'today': today,
		},
	)


@login_required
def apply_opportunity(request, opportunity_id):
	if request.user.role != 'player':
		messages.error(request, 'Only players can apply for opportunities.')
		return redirect('scout_dashboard')

	_auto_expire_passed_deadline_opportunities()
	opportunity = get_object_or_404(Opportunity, id=opportunity_id)
	today = timezone.localdate()
	if (not opportunity.is_active) or (opportunity.deadline < today):
		messages.error(request, 'This opportunity is expired. You can view it but cannot apply.')
		return redirect('view_opportunities')

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

	_auto_expire_passed_deadline_opportunities()
	selected_view = request.GET.get('view', 'available').strip().lower()
	if selected_view not in {'available', 'history'}:
		selected_view = 'available'
	is_verified = getattr(request.user.scout_profile, 'verified', False)
	if not is_verified:
		messages.warning(request, 'Your scout account is pending verification. Posting is disabled until approved by admin.')

	if request.method == 'POST':
		if not is_verified:
			return redirect('post_opportunity')
		form = OpportunityForm(request.POST, request.FILES, scout=request.user)
		if form.is_valid():
			opportunity = form.save(commit=False)
			opportunity.scout = request.user
			opportunity.save()
			messages.success(request, 'Opportunity posted successfully.')
			return redirect('post_opportunity')
	else:
		form = OpportunityForm(scout=request.user)

	available_opportunities = Opportunity.objects.filter(scout=request.user, is_active=True).order_by('deadline', '-created_at')
	history_opportunities = Opportunity.objects.filter(scout=request.user, is_active=False).order_by('-updated_at', '-created_at')
	return render(
		request,
		'scouts/postopportunity.html',
		{
			'form': form,
			'available_opportunities': available_opportunities,
			'history_opportunities': history_opportunities,
			'selected_view': selected_view,
			'is_verified': is_verified,
		},
	)


@login_required
def manage_posted_opportunities(request):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can manage posted opportunities.')
		return redirect('player_dashboard')

	_auto_expire_passed_deadline_opportunities()
	opportunities = (
		Opportunity.objects.filter(scout=request.user)
		.prefetch_related('applications__player')
	)

	return render(
		request,
		'scouts/manage_opportunities.html',
		{'opportunities': opportunities, 'today': timezone.localdate()},
	)


@login_required
def close_opportunity_early(request, opportunity_id):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can update opportunity status.')
		return redirect('player_dashboard')

	if request.method != 'POST':
		return redirect('manage_posted_opportunities')

	opportunity = get_object_or_404(Opportunity, id=opportunity_id, scout=request.user)
	today = timezone.localdate()

	if not opportunity.is_active:
		messages.info(request, 'Opportunity is already closed.')
		return redirect('manage_posted_opportunities')

	if opportunity.deadline < today:
		messages.info(request, 'This opportunity has already expired automatically after deadline.')
		return redirect('manage_posted_opportunities')

	if not opportunity.max_applications:
		messages.warning(request, 'Set an application limit when posting if you want to close before deadline.')
		return redirect('manage_posted_opportunities')

	applications_count = opportunity.applications.count()
	if applications_count < opportunity.max_applications:
		messages.warning(
			request,
			f'Cannot close early yet. Applications: {applications_count}/{opportunity.max_applications}.',
		)
		return redirect('manage_posted_opportunities')

	opportunity.is_active = False
	opportunity.save(update_fields=['is_active', 'updated_at'])
	messages.success(request, f'Opportunity "{opportunity.title}" closed early successfully.')
	return redirect('manage_posted_opportunities')


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
