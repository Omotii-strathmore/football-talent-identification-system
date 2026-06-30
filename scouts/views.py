from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from opportunities.models import Application, Opportunity
from players.models import PlayerProfile, PlayerVideo
from scouts.forms import ScoutEditDetailsForm
from scouts.models import ScoutVideoFeedback


def _recommended_position_from_specialization(specialization):
    specialization_text = (specialization or '').strip().lower()

    if any(keyword in specialization_text for keyword in ['goal', 'goalkeeping', 'goalkeeper']):
        return 'Goalkeeper'
    if any(keyword in specialization_text for keyword in ['defender', 'defending', 'defence', 'defense', 'backline']):
        return 'Defender'
    if any(keyword in specialization_text for keyword in ['midfielder', 'midfield', 'playmaker']):
        return 'Midfielder'
    if any(keyword in specialization_text for keyword in ['forward', 'striker', 'attack', 'attacking', 'winger']):
        return 'Forward'
    return None


@login_required
def dashboard(request):
    if request.user.role != 'scout':
        messages.error(request, 'Only scouts can access the scout dashboard.')
        return redirect('player_dashboard')

    scout_profile = request.user.scout_profile
    first_name = (request.user.full_name or 'Scout').split()[0]
    posted_opportunities = Opportunity.objects.filter(scout=request.user)
    active_opportunities = posted_opportunities.filter(is_active=True)
    total_applications = Application.objects.filter(opportunity__scout=request.user).count()
    recent_opportunities = posted_opportunities[:5]
    recent_applications = (
        Application.objects.select_related('opportunity', 'player')
        .filter(opportunity__scout=request.user)[:5]
    )

    return render(
        request,
        'scouts/scoutdashboard.html',
        {
            'scout_profile': scout_profile,
            'first_name': first_name,
            'posted_count': posted_opportunities.count(),
            'active_count': active_opportunities.count(),
            'applications_count': total_applications,
            'recent_opportunities': recent_opportunities,
            'recent_applications': recent_applications,
        }
    )


@login_required
def player_directory(request):
    if request.user.role != 'scout':
        messages.error(request, 'Only scouts can view player profiles.')
        return redirect('player_dashboard')

    if request.method == 'POST':
        video_id = request.POST.get('video_id')
        comment = request.POST.get('comment', '').strip()
        current_query = request.POST.get('current_query', '').strip()

        if not video_id:
            messages.error(request, 'Could not identify the selected video.')
        else:
            video = get_object_or_404(PlayerVideo.objects.select_related('profile'), id=video_id)
            if comment:
                ScoutVideoFeedback.objects.update_or_create(
                    scout=request.user,
                    video=video,
                    defaults={'comment': comment},
                )
                messages.success(request, f'Feedback saved for video "{video.title}".')
            else:
                messages.info(request, 'Feedback box was empty. Nothing was saved.')

        redirect_url = reverse('scout_player_directory')
        if current_query:
            redirect_url = f'{redirect_url}?{current_query}'
        return redirect(redirect_url)

    scout_specialization = (request.user.scout_profile.specialization or '').strip().lower()
    is_general_scout = scout_specialization == 'general'
    recommended_position = None if is_general_scout else _recommended_position_from_specialization(scout_specialization)

    profiles = (
        PlayerProfile.objects.select_related('user')
        .prefetch_related('videos')
        .all()
    )

    position_param_present = 'position' in request.GET
    selected_position = request.GET.get('position', '').strip()
    selected_location = request.GET.get('location', '').strip()
    selected_age = request.GET.get('age', '').strip()
    selected_age_range = request.GET.get('age_range', '').strip()

    # Default to specialization-matched position for non-general scouts until they choose another.
    if not selected_position and recommended_position and not position_param_present:
        selected_position = recommended_position

    if selected_position:
        profiles = profiles.filter(position=selected_position)

    if selected_location:
        profiles = profiles.filter(location__icontains=selected_location)

    if selected_age:
        try:
            profiles = profiles.filter(age=int(selected_age))
        except ValueError:
            messages.error(request, 'Age filter must be a valid number.')

    if selected_age_range:
        try:
            start_age, end_age = selected_age_range.split('-')
            start_age = int(start_age)
            end_age = int(end_age)
            profiles = profiles.filter(age__gte=start_age, age__lte=end_age)
        except (ValueError, TypeError):
            messages.error(request, 'Select a valid age range.')

    all_locations = (
        PlayerProfile.objects.exclude(location='')
        .values_list('location', flat=True)
        .distinct()
        .order_by('location')
    )
    all_ages = (
        PlayerProfile.objects.values_list('age', flat=True)
        .distinct()
        .order_by('age')
    )

    age_ranges = []
    start_age = 12
    max_age = 28
    while start_age <= max_age:
        end_age = min(start_age + 2, max_age)
        label = f'{start_age}-{end_age}'
        age_ranges.append((label, label))
        start_age = end_age + 1

    profiles = list(profiles)
    profile_ids = [profile.id for profile in profiles]
    feedback_map = {
        entry.video_id: entry
        for entry in ScoutVideoFeedback.objects.filter(
            scout=request.user,
            video__profile_id__in=profile_ids,
        )
    }
    for profile in profiles:
        for video in profile.videos.all():
            video.current_scout_feedback = feedback_map.get(video.id)

    return render(
        request,
        'scouts/playerdirectory.html',
        {
            'profiles': profiles,
            'positions': PlayerProfile.POSITION_CHOICES,
            'locations': all_locations,
            'ages': all_ages,
            'age_ranges': age_ranges,
            'selected_position': selected_position,
            'selected_location': selected_location,
            'selected_age': selected_age,
            'selected_age_range': selected_age_range,
            'recommended_position': recommended_position,
            'is_general_scout': is_general_scout,
        }
    )


@login_required
def player_recommendations(request):
    if request.user.role != 'scout':
        messages.error(request, 'Only scouts can view player recommendations.')
        return redirect('player_dashboard')

    scout_profile = request.user.scout_profile
    recommended_position = _recommended_position_from_specialization(scout_profile.specialization)

    profiles = PlayerProfile.objects.select_related('user').prefetch_related('videos').all()
    if recommended_position:
        profiles = profiles.filter(position=recommended_position)

    return render(
        request,
        'scouts/player_recommendations.html',
        {
            'profiles': profiles,
            'specialization': scout_profile.specialization,
            'recommended_position': recommended_position,
        },
    )


@login_required
def edit_details(request):
    if request.user.role != 'scout':
        messages.error(request, 'Only scouts can edit scout details.')
        return redirect('player_dashboard')

    scout_profile = request.user.scout_profile

    if request.method == 'POST':
        form = ScoutEditDetailsForm(request.POST, request.FILES, instance=scout_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Scout details updated successfully.')
            return redirect('scout_edit_details')
    else:
        form = ScoutEditDetailsForm(instance=scout_profile)

    return render(
        request,
        'scouts/edit_details.html',
        {
            'form': form,
            'scout_profile': scout_profile,
        },
    )