from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from players.categories import can_apply

from .forms import ApplicationForm, OpportunityForm
from players.models import PlayerProfile
from .models import Application, Opportunity


def _auto_expire_passed_deadline_opportunities():
	today = timezone.localdate()
	Opportunity.objects.filter(is_active=True, deadline__lt=today).update(is_active=False)


def _category_filter(queryset, category):
	"""Stars or Starlets trials, together with those open to all."""
	if category in ('stars', 'starlets'):
		return queryset.filter(category__in=[category, 'open'])
	return queryset


def public_opportunities(request):
	_auto_expire_passed_deadline_opportunities()
	selected_view = request.GET.get('view', 'available').strip().lower()
	if selected_view not in {'available', 'history'}:
		selected_view = 'available'

	selected_category = request.GET.get('cat', 'all')
	if selected_category not in ('all', 'stars', 'starlets'):
		selected_category = 'all'

	today = timezone.localdate()
	available_opportunities = _category_filter(Opportunity.objects.filter(is_active=True), selected_category).order_by('deadline', '-created_at')
	history_opportunities = _category_filter(Opportunity.objects.filter(is_active=False), selected_category).order_by('-updated_at', '-created_at')
	for opportunity in available_opportunities:
		opportunity.days_left = (opportunity.deadline - today).days
	return render(
		request,
		'opportunities/public_opportunities.html',
		{
			'available_opportunities': available_opportunities,
			'history_opportunities': history_opportunities,
			'selected_view': selected_view,
			'selected_category': selected_category,
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
	# Players see trials for their own category (Stars or Starlets) and those open to all first.
	player_category = getattr(PlayerProfile.objects.filter(user=request.user).first(), 'category', '') or ''
	selected_category = request.GET.get('cat', player_category or 'all')
	if selected_category not in ('all', 'stars', 'starlets'):
		selected_category = 'all'
	today = timezone.localdate()
	available_opportunities = _category_filter(Opportunity.objects.filter(is_active=True), selected_category).order_by('deadline', '-created_at')
	history_opportunities = _category_filter(Opportunity.objects.filter(is_active=False), selected_category).order_by('-updated_at', '-created_at')
	for opportunity in available_opportunities:
		opportunity.days_left = (opportunity.deadline - today).days
		opportunity.can_apply = bool(player_category) and can_apply(player_category, opportunity.category)
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
			'selected_category': selected_category,
			'player_category': player_category,
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

	profile = PlayerProfile.objects.filter(user=request.user).first()
	if profile and profile.needs_guardian_approval:
		messages.error(request, 'Your parent or guardian needs to approve your account before you can apply for trials.')
		return redirect('view_opportunities')

	player_category = getattr(profile, 'category', '') or ''
	if not player_category:
		messages.info(request, 'First tell us whether you play with the Stars or the Starlets (on your dashboard), then apply.')
		return redirect('player_dashboard')
	if not can_apply(player_category, opportunity.category):
		wanted = "Starlets (women's football)" if opportunity.category == 'starlets' else "Stars (men's football)"
		messages.error(request, f'This opportunity is for {wanted}. You can apply to trials for your own category or ones open to all. If your category is wrong, change it on your profile.')
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

	applications = list(Application.objects.select_related('opportunity').filter(player=request.user))
	mark_trial_stages(applications)
	status_counts = {
		'pending': sum(1 for a in applications if a.status == 'pending'),
		'shortlisted': sum(1 for a in applications if a.status == 'shortlisted'),
		'rejected': sum(1 for a in applications if a.status == 'rejected'),
	}
	return render(
		request,
		'players/applications.html',
		{'applications': applications, 'status_counts': status_counts, 'trial_followup': pending_followup(request.user)},
	)


def mark_trial_stages(applications):
	"""For shortlisted players: before the trial day, on the day, or after it."""
	today = timezone.localdate()
	for application in applications:
		day = application.opportunity.trial_day
		application.trial_day = day
		application.trial_stage = 'before' if day > today else ('today' if day == today else 'after')
	return applications


def pending_followup(user):
	"""The oldest trial this shortlisted player has not yet told us about (attended or not), if any."""
	if not getattr(user, 'is_authenticated', False) or user.role != 'player':
		return None
	today = timezone.localdate()
	for application in (Application.objects.select_related('opportunity')
						.filter(player=user, status='shortlisted', attended__isnull=True).order_by('opportunity__deadline')):
		if application.opportunity.trial_day < today:
			return application
	return None


@login_required
@require_POST
def application_attendance(request, application_id):
	"""The player says whether they went to a trial they were shortlisted for."""
	application = get_object_or_404(Application.objects.select_related('opportunity'), id=application_id,
									player=request.user, status='shortlisted')
	if application.opportunity.trial_day >= timezone.localdate():
		return JsonResponse({'ok': False, 'message': 'You can tell us after the trial day.'}, status=400)
	answer = request.POST.get('attended')
	if answer not in ('yes', 'no'):
		return JsonResponse({'ok': False, 'message': 'Please choose Yes or No.'}, status=400)
	note = (request.POST.get('note') or '').strip()[:1000]
	application.attended = answer == 'yes'
	application.attendance_note = note
	application.absence_reason = ''
	if not application.attended:
		reason = request.POST.get('reason', '')
		if reason not in dict(Application.ABSENCE_CHOICES):
			return JsonResponse({'ok': False, 'message': 'Please choose a reason.'}, status=400)
		if reason == 'other' and not note:
			return JsonResponse({'ok': False, 'message': 'Please tell us a little more.'}, status=400)
		application.absence_reason = reason
	application.attendance_answered_at = timezone.now()
	application.save(update_fields=['attended', 'absence_reason', 'attendance_note', 'attendance_answered_at'])
	return JsonResponse({'ok': True})


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
def edit_posted_opportunity(request, opportunity_id):
	if request.user.role != 'scout':
		messages.error(request, 'Only scouts can edit posted opportunities.')
		return redirect('player_dashboard')

	opportunity = get_object_or_404(Opportunity, id=opportunity_id, scout=request.user)
	today = timezone.localdate()

	if request.method == 'POST':
		was_inactive = not opportunity.is_active
		form = OpportunityForm(request.POST, request.FILES, instance=opportunity, scout=request.user)
		if form.is_valid():
			updated_opportunity = form.save(commit=False)
			reactivated = False
			if was_inactive and updated_opportunity.deadline >= today:
				updated_opportunity.is_active = True
				reactivated = True

			updated_opportunity.save()
			if reactivated:
				messages.success(request, f'Opportunity "{updated_opportunity.title}" updated and reactivated.')
			else:
				messages.success(request, f'Opportunity "{updated_opportunity.title}" updated successfully.')
			return redirect('manage_posted_opportunities')
	else:
		form = OpportunityForm(instance=opportunity, scout=request.user)

	return render(
		request,
		'scouts/edit_opportunity.html',
		{
			'form': form,
			'opportunity': opportunity,
		},
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
