from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from opportunities.models import Application
from players.forms import PlayerProfileForm, PlayerVideoForm
from players.guardian import can_resend, mask_email, profile_from_token, send_guardian_email
from players.models import PlayerProfile, PlayerVideo
from opportunities.views import pending_followup
from players.badges import player_badges
from scouts.models import FairPlayAward, ScoutVideoFeedback

def _profile_strength(profile, videos_count):
    """How complete a profile is (0-100), and the most useful next step."""
    steps = [
        (bool(profile.profile_photo), 'Add a clear profile photo'),
        (videos_count >= 1, 'Upload your first video'),
        (bool((profile.bio or '').strip()), 'Write a short bio about your game'),
        (bool(profile.secondary_position), 'Add a second position you can play'),
        (bool(profile.height_cm and profile.weight_kg), 'Add your height and weight'),
        (bool((profile.football_experience or '').strip()), 'Describe your football experience'),
        (bool(profile.current_club or profile.previous_club), 'Add your current or previous club'),
        (videos_count >= 3, 'Upload 3 videos for a full highlight reel'),
    ]
    done = sum(1 for ok, _ in steps if ok)
    next_tip = next((tip for ok, tip in steps if not ok), '')
    return {'percent': round(done * 100 / len(steps)), 'next': next_tip}


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

    unread_feedback_count = feedback_entries.filter(is_seen=False).count() if profile else 0
    videos = profile.videos.all() if profile else []

    if unread_feedback_count:
        messages.info(request, f'You have {unread_feedback_count} unread scout feedback item(s).')
    my_badges = player_badges(profile, video_count=videos_count, application_count=applications_count) if profile else []

    return render(
        request,
        'players/playerdashboard.html',
        {
            'profile': profile,
            'first_name': first_name,
            'applications_count': applications_count,
            'videos_count': videos_count,
            'videos': videos,
            'my_badges': my_badges,
            'trial_followup': pending_followup(request.user),
            'badges_earned': sum(1 for badge in my_badges if badge['earned']),
            'strength': _profile_strength(profile, videos_count) if profile else None,
            'new_fair_play': (
                FairPlayAward.objects.select_related('scout').filter(
                    profile=profile, created_at__gte=timezone.now() - timedelta(days=14))
                if profile else []
            ),
            'guardian_pending': bool(profile and profile.needs_guardian_approval),
            'guardian_email_masked': mask_email(profile.guardian_email) if profile and profile.guardian_email else '',
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
        old_contact_email = profile.contact_email
        form = PlayerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            from users.email_change import contact_email_changed
            contact_email_changed(profile, old_contact_email)
            if profile.contact_email and not profile.contact_email_verified_at:
                messages.success(request, 'Profile updated. Please verify your new contact email below so scouts can see it.')
            else:
                messages.success(request, 'Profile updated successfully.')
            return redirect('player_profile')
    else:
        form = PlayerProfileForm(instance=profile)

    trait_list = []
    if profile.special_traits:
        trait_list = [trait.strip() for trait in profile.special_traits.split(',') if trait.strip()]

    return render(
        request,
        'players/playerprofile.html',
        {
            'profile': profile,
            'form': form,
            'edit_mode': edit_mode,
            'videos': profile.videos.all(),
            'trait_list': trait_list,
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
        feedback_id = request.POST.get('feedback_id')
        if feedback_id:
            feedback = get_object_or_404(ScoutVideoFeedback, id=feedback_id, video__profile=profile)
            history_text = request.POST.get('player_reply_history')
            if history_text is not None:
                if not feedback.player_reply_editable:
                    messages.error(request, f'The {ScoutVideoFeedback.REPLY_EDIT_WINDOW_MINUTES}-minute edit window for your reply has closed. Add a new reply instead.')
                    return redirect('upload_video')
                feedback.player_reply = history_text.strip()
                feedback.is_seen = True
                feedback.seen_at = timezone.now()
                feedback.save(update_fields=['player_reply', 'is_seen', 'seen_at', 'updated_at'])
                messages.success(request, 'Previous replies updated successfully.')
                return redirect('upload_video')

            reply = request.POST.get('player_reply', '').strip()
            reaction = request.POST.get('player_reaction', '').strip()
            update_fields = ['is_seen', 'seen_at', 'updated_at']

            if reply:
                reply_stamp = timezone.localtime().strftime('%Y-%m-%d %H:%M')
                reply_line = f'Player ({reply_stamp}): {reply}'
                if feedback.player_reply:
                    feedback.player_reply = f'{feedback.player_reply}\n{reply_line}'
                else:
                    feedback.player_reply = reply_line
                feedback.player_reply_at = timezone.now()
                update_fields.append('player_reply')
                update_fields.append('player_reply_at')

            if reaction:
                feedback.player_reaction = reaction
                update_fields.append('player_reaction')

            feedback.is_seen = True
            feedback.seen_at = timezone.now()
            feedback.save(update_fields=update_fields)
            if reply and reaction:
                messages.success(request, 'Your reply and reaction were saved.')
            elif reply:
                messages.success(request, 'Your reply was saved.')
            elif reaction:
                messages.success(request, 'Your reaction was saved.')
            else:
                messages.info(request, 'Feedback marked as seen.')
            return redirect('upload_video')

        form = PlayerVideoForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.profile = profile
            video.save()
            messages.success(request, 'Video uploaded successfully.')
            return redirect('upload_video')
    else:
        form = PlayerVideoForm()

    videos = profile.videos.all()

    ScoutVideoFeedback.objects.filter(video__profile=profile, is_seen=False).update(
        is_seen=True,
        seen_at=timezone.now(),
    )

    return render(
        request,
        'players/uploadvideo.html',
        {
            'form': form,
            'videos': videos,
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

def guardian_review(request, token):
    """Public page a parent/guardian opens from the email to approve or decline a player under 18."""
    profile = profile_from_token(token)
    if profile is None:
        return render(request, 'players/guardian_review.html', {'invalid': True}, status=404)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        if decision == 'approve':
            profile.guardian_approved_at = timezone.now()
            profile.guardian_declined_at = None
        elif decision == 'decline':
            profile.guardian_approved_at = None
            profile.guardian_declined_at = timezone.now()
        profile.save(update_fields=['guardian_approved_at', 'guardian_declined_at'])
        return redirect('guardian_review', token=token)

    return render(request, 'players/guardian_review.html', {'profile': profile, 'token': token})


@login_required
def guardian_resend(request):
    """Let a player under 18 resend the approval email, optionally to a corrected address."""
    if request.method != 'POST' or request.user.role != 'player':
        return redirect('player_dashboard')
    profile = get_object_or_404(PlayerProfile, user=request.user)
    if not profile.needs_guardian_approval:
        return redirect('player_dashboard')

    new_email = request.POST.get('guardian_email', '').strip().lower()
    if new_email and new_email != profile.guardian_email:
        field = forms.EmailField()
        try:
            new_email = field.clean(new_email)
        except forms.ValidationError:
            messages.error(request, 'Please enter a valid email address for your parent or guardian.')
            return redirect('player_dashboard')
        if new_email == request.user.email.lower():
            messages.error(request, 'This must be your parent or guardian\'s own email, not yours.')
            return redirect('player_dashboard')
        profile.guardian_email = new_email
        profile.guardian_email_sent_at = None
        profile.guardian_declined_at = None
        profile.save(update_fields=['guardian_email', 'guardian_email_sent_at', 'guardian_declined_at'])
    elif not can_resend(profile):
        messages.info(request, 'We just sent it. Please wait two minutes before sending again.')
        return redirect('player_dashboard')

    if send_guardian_email(request, profile):
        messages.success(request, f'Approval email sent to {mask_email(profile.guardian_email)}.')
    else:
        messages.error(request, 'We could not send the email right now. Please try again later.')
    return redirect('player_dashboard')


@login_required
@require_POST
def set_category(request):
    """The one-time Stars / Starlets question on the dashboard for players who joined before categories."""
    profile = PlayerProfile.objects.filter(user=request.user).first()
    category = request.POST.get('category', '')
    if profile and category in ('stars', 'starlets'):
        profile.category = category
        profile.save(update_fields=['category'])
        name = 'Stars' if category == 'stars' else 'Starlets'
        messages.success(request, f'Thank you! You are now listed with the {name}. You can change this on your profile.')
    return redirect('player_dashboard')
