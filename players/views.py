from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from opportunities.models import Application
from players.forms import PlayerProfileForm, PlayerVideoForm
from players.models import PlayerProfile, PlayerVideo
from scouts.models import ScoutVideoFeedback

@login_required
def dashboard(request):
    if request.user.role != 'player':
        messages.error(request, 'Only players can access the player dashboard.')
        return redirect('scout_dashboard')

    profile = PlayerProfile.objects.filter(user=request.user).first()
    applications_count = Application.objects.filter(player=request.user).count()
    videos_count = profile.videos.count() if profile else 0
    first_name = (request.user.full_name or 'Player').split()[0]
    feedback_entries = (
        ScoutVideoFeedback.objects.select_related('scout', 'scout__scout_profile', 'video')
        .filter(video__profile=profile)
        .order_by('-updated_at')
        if profile
        else ScoutVideoFeedback.objects.none()
    )

    if request.method == 'POST':
        feedback_id = request.POST.get('feedback_id')
        if feedback_id:
            feedback = get_object_or_404(ScoutVideoFeedback, id=feedback_id, video__profile=profile)
            reply = request.POST.get('player_reply', '').strip()
            reaction = request.POST.get('player_reaction', '').strip()
            feedback.player_reply = reply
            feedback.player_reaction = reaction
            feedback.is_seen = True
            feedback.seen_at = timezone.now()
            feedback.save(update_fields=['player_reply', 'player_reaction', 'is_seen', 'seen_at', 'updated_at'])
            if reply or reaction:
                messages.success(request, 'Your reply has been sent to the scout.')
            else:
                messages.info(request, 'Feedback marked as seen.')
            return redirect('player_dashboard')

    unread_feedback_count = feedback_entries.filter(is_seen=False).count() if profile else 0
    videos = profile.videos.all() if profile else []

    if unread_feedback_count:
        messages.info(request, f'You have {unread_feedback_count} unread scout feedback item(s).')

    return render(
        request,
        'players/playerdashboard.html',
        {
            'profile': profile,
            'first_name': first_name,
            'applications_count': applications_count,
            'videos_count': videos_count,
            'feedback_entries': feedback_entries,
            'unread_feedback_count': unread_feedback_count,
            'videos': videos,
        }
    )


@login_required
def profile_view(request):
    if request.user.role != 'player':
        messages.error(request, 'Only players can access player profile.')
        return redirect('scout_dashboard')

    profile = PlayerProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'Complete registration first to create your profile.')
        return redirect('register')

    edit_mode = request.GET.get('edit') == 'true'

    if request.method == 'POST':
        form = PlayerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('player_profile')
    else:
        form = PlayerProfileForm(instance=profile)

    return render(
        request,
        'players/playerprofile.html',
        {
            'profile': profile,
            'form': form,
            'edit_mode': edit_mode,
            'videos': profile.videos.all(),
        },
    )


@login_required
def upload_video(request):
    if request.user.role != 'player':
        messages.error(request, 'Only players can upload videos.')
        return redirect('scout_dashboard')

    profile = PlayerProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'Complete registration first to upload videos.')
        return redirect('register')

    if request.method == 'POST':
        form = PlayerVideoForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.profile = profile
            video.save()
            messages.success(request, 'Video uploaded successfully.')
            return redirect('upload_video')
    else:
        form = PlayerVideoForm()

    return render(
        request,
        'players/uploadvideo.html',
        {
            'form': form,
            'videos': profile.videos.all(),
        },
    )


@login_required
def delete_video(request, video_id):
    if request.user.role != 'player':
        messages.error(request, 'Only players can delete videos.')
        return redirect('scout_dashboard')

    if request.method != 'POST':
        return redirect('upload_video')

    profile = PlayerProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'Complete registration first to manage videos.')
        return redirect('register')

    video = get_object_or_404(PlayerVideo, id=video_id, profile=profile)
    video_title = video.title

    # Remove the file from storage before deleting the database row.
    if video.video_file:
        video.video_file.delete(save=False)
    video.delete()

    messages.success(request, f'Video "{video_title}" deleted successfully.')
    return redirect('upload_video')