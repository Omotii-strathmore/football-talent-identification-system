from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from opportunities.models import Application, Opportunity
from players.models import PlayerProfile


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

    profiles = PlayerProfile.objects.select_related('user').prefetch_related('videos').all()

    filter_by = request.GET.get('filter_by', '').strip().lower()
    filter_value = request.GET.get('filter_value', '').strip()

    if filter_by == 'position' and filter_value:
        profiles = profiles.filter(position=filter_value)
    elif filter_by == 'location' and filter_value:
        profiles = profiles.filter(location__icontains=filter_value)
    elif filter_by == 'age' and filter_value:
        try:
            profiles = profiles.filter(age=int(filter_value))
        except ValueError:
            messages.error(request, 'Age filter must be a valid number.')

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

    return render(
        request,
        'scouts/playerdirectory.html',
        {
            'profiles': profiles,
            'filter_by': filter_by,
            'filter_value': filter_value,
            'positions': PlayerProfile.POSITION_CHOICES,
            'locations': all_locations,
            'ages': all_ages,
        }
    )