from datetime import timedelta
import logging

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core import signing
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone, dateparse
from django.views.decorators.http import require_POST
from users.emails import send_branded_email

from opportunities.models import Application
from players.forms import PlayerProfileForm, PlayerVideoForm
from players.guardian import can_resend, mask_email, profile_from_token, send_guardian_email, visible_to_scouts_q
from players.models import PlayerProfile, PlayerVideo, PlayerJourneyGoal, PlayerJourneyCheckIn
from opportunities.views import pending_followup
from players.badges import player_badges
from scouts.models import FairPlayAward, ScoutVideoFeedback, ScoutPlayerContactRequest

CONTACT_REQUEST_TOKEN_SALT = 'talanta-soka.guardian-contact-request'
CONTACT_REQUEST_TOKEN_MAX_AGE = 60 * 60 * 24 * 7
logger = logging.getLogger(__name__)

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
    last_checkin = profile.journey_checkins.first() if profile else None
    checkin_reference = last_checkin.created_at if last_checkin else (profile.created_at if profile else None)
    next_checkin_at = checkin_reference + timedelta(days=90) if checkin_reference else None
    journey_checkin_due = bool(next_checkin_at and timezone.now() >= next_checkin_at)

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
            'journey_goals': profile.journey_goals.all() if profile else [],
            'journey_checkins': profile.journey_checkins.all()[:5] if profile else [],
            'journey_checkin_due': journey_checkin_due,
            'next_checkin_at': next_checkin_at,
            'contact_requests': (
                ScoutPlayerContactRequest.objects.select_related('scout', 'scout__scout_profile')
                .filter(profile=profile).order_by('-updated_at')
                if profile else []
            ),
        }
    )


@login_required
def player_community(request):
    if request.user.role != 'player':
        messages.error(request, 'The Player Community is available to signed-in players.')
        return redirect('scout_dashboard')
    search = request.GET.get('q', '').strip()[:80]
    profiles = (
        PlayerProfile.objects.select_related('user')
        .prefetch_related('videos', 'journey_goals', 'journey_checkins')
        .filter(visible_to_scouts_q())
        .filter(Q(share_profile_with_players=True) | Q(share_journey_with_community=True))
        .exclude(user=request.user)
        .order_by('full_name', 'id')
    )
    if search:
        profiles = profiles.filter(
            Q(full_name__icontains=search)
            | Q(position__icontains=search)
            | Q(location__icontains=search)
        )
    page_obj = Paginator(profiles, 12).get_page(request.GET.get('page'))
    return render(
        request,
        'players/player_community.html',
        {
            'profiles': page_obj.object_list,
            'page_obj': page_obj,
            'search': search,
        },
    )


@login_required
@require_POST
def journey_update(request):
    if request.user.role != 'player':
        messages.error(request, 'Only players can update a player journey.')
        return redirect('scout_dashboard')
    profile = PlayerProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'Complete registration before updating your journey.')
        return redirect('complete_profile')

    action = request.POST.get('action', '')
    if action == 'add_goal':
        title = request.POST.get('title', '').strip()
        target_date_value = request.POST.get('target_date', '').strip()
        target_date = dateparse.parse_date(target_date_value) if target_date_value else None
        if not title or len(title) > 180:
            messages.error(request, 'Enter a goal of up to 180 characters.')
        elif target_date_value and not target_date:
            messages.error(request, 'Enter a valid target date.')
        else:
            PlayerJourneyGoal.objects.create(profile=profile, title=title, target_date=target_date)
            messages.success(request, 'Your football goal was added.')
    elif action == 'check_in':
        update = request.POST.get('update', '').strip()
        next_step = request.POST.get('next_step', '').strip()
        if not update or len(update) > 1200 or len(next_step) > 300:
            messages.error(request, 'Write an update (up to 1,200 characters) and keep your next step under 300 characters.')
        else:
            PlayerJourneyCheckIn.objects.create(profile=profile, update=update, next_step=next_step)
            messages.success(request, 'Your progress check-in was saved.')
    elif action == 'complete_goal':
        goal = get_object_or_404(PlayerJourneyGoal, pk=request.POST.get('goal_id'), profile=profile)
        goal.is_complete = not goal.is_complete
        goal.save(update_fields=['is_complete', 'updated_at'])
        messages.success(request, 'Goal progress updated.')
    elif action == 'set_visibility':
        visibility = request.POST.get('visibility')
        if visibility not in ('private', 'public'):
            messages.error(request, 'Choose private or public progress visibility.')
        else:
            profile.share_journey_with_community = visibility == 'public'
            profile.save(update_fields=['share_journey_with_community'])
            visibility_label = 'signed-in players and verified scouts' if visibility == 'public' else 'only you'
            messages.success(request, f'Your progress is now visible to {visibility_label}.')
    else:
        messages.error(request, 'Choose a valid journey update.')
    return redirect('player_dashboard')


def _send_contact_request_to_guardian(request, contact_request):
    profile = contact_request.profile
    token = signing.dumps(
        {'r': contact_request.pk, 'e': profile.guardian_email.lower()},
        salt=CONTACT_REQUEST_TOKEN_SALT,
    )
    link = request.build_absolute_uri(reverse('guardian_contact_review', args=[token]))
    scout_name = contact_request.scout.full_name
    organization = contact_request.scout.scout_profile.organization
    subject = f'Parent approval requested for {profile.full_name} on Talanta Soka'
    text = (
        f'Hello {profile.guardian_name or "Parent or guardian"},\n\n'
        f'{profile.full_name} has accepted a contact request from {scout_name}, with {organization}.\n\n'
        'Please review this request and approve or decline whether the scout may receive the '
        'player contact details they have chosen to share:\n'
        f'{link}\n\n'
        'The scout will not receive contact details unless you approve. This approval is separate '
        'from the permission for scouts to view the player profile.\n\n'
        f'Questions? Contact {settings.SUPPORT_EMAIL}.\n\nTalanta Soka'
    )
    try:
        send_branded_email(
            subject,
            text,
            'guardian_contact_request.html',
            {
                'link': link,
                'guardian_name': profile.guardian_name or 'Parent or guardian',
                'player_name': profile.full_name,
                'scout_name': scout_name,
                'organization': organization,
                'message': contact_request.message,
            },
            [profile.guardian_email],
            banner='team',
        )
    except Exception:
        logger.exception(
            'Failed to send guardian contact-request approval for request %s', contact_request.pk
        )
        return False
    contact_request.guardian_email_sent_at = timezone.now()
    contact_request.save(update_fields=['guardian_email_sent_at', 'updated_at'])
    return True


@login_required
@require_POST
def respond_to_contact_request(request, request_id):
    if request.user.role != 'player':
        messages.error(request, 'Only players can respond to contact requests.')
        return redirect('scout_dashboard')
    profile = PlayerProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'Complete your player profile before responding.')
        return redirect('complete_profile')
    contact_request = get_object_or_404(
        ScoutPlayerContactRequest.objects.select_related('scout', 'scout__scout_profile'),
        pk=request_id,
        profile=profile,
    )
    decision = request.POST.get('decision')
    if decision == 'resend' and contact_request.status == 'guardian_pending':
        sent_at = contact_request.guardian_email_sent_at
        if sent_at and (timezone.now() - sent_at).total_seconds() < 120:
            messages.info(request, 'Please wait a moment before resending the guardian approval email.')
        elif _send_contact_request_to_guardian(request, contact_request):
            messages.success(request, 'A new guardian approval email was sent.')
        else:
            messages.error(request, 'We could not resend the guardian approval email. Please try again later or contact support.')
        return redirect('player_dashboard')
    if contact_request.status != 'pending':
        messages.error(request, 'This contact request is no longer awaiting your response.')
        return redirect('player_dashboard')
    if decision == 'decline':
        contact_request.status = 'declined'
        contact_request.player_decided_at = timezone.now()
        contact_request.save(update_fields=['status', 'player_decided_at', 'updated_at'])
        messages.success(request, 'You declined the scout contact request. No contact details were shared.')
    elif decision == 'accept':
        if profile.is_minor and not profile.guardian_email:
            messages.error(request, 'Add your parent or guardian email to your profile before accepting this request.')
            return redirect('player_dashboard')
        contact_request.player_decided_at = timezone.now()
        if profile.is_minor:
            contact_request.status = 'guardian_pending'
            contact_request.save(update_fields=['status', 'player_decided_at', 'updated_at'])
            if _send_contact_request_to_guardian(request, contact_request):
                messages.success(request, 'Your parent or guardian has been emailed to approve the contact request.')
            else:
                messages.error(request, 'The request was saved, but we could not email your parent or guardian. Please try again later or contact support.')
        else:
            contact_request.status = 'accepted'
            contact_request.save(update_fields=['status', 'player_decided_at', 'updated_at'])
            messages.success(request, 'You accepted the request. The scout can see your contact details only if you have also enabled contact sharing in your profile.')
    else:
        messages.error(request, 'Choose whether to accept or decline the request.')
    return redirect('player_dashboard')


def guardian_contact_review(request, token):
    try:
        token_data = signing.loads(
            token,
            salt=CONTACT_REQUEST_TOKEN_SALT,
            max_age=CONTACT_REQUEST_TOKEN_MAX_AGE,
        )
    except signing.BadSignature:
        messages.error(request, 'This approval link is invalid or has expired.')
        return redirect('home')
    contact_request = (
        ScoutPlayerContactRequest.objects.select_related('profile', 'scout', 'scout__scout_profile')
        .filter(pk=token_data.get('r'), status='guardian_pending')
        .first()
    )
    if not contact_request or contact_request.profile.guardian_email.lower() != token_data.get('e'):
        messages.error(request, 'This contact approval request is no longer available.')
        return redirect('home')
    if request.method == 'POST':
        if request.POST.get('decision') == 'accept':
            contact_request.status = 'accepted'
            contact_request.guardian_approved_at = timezone.now()
            contact_request.save(update_fields=['status', 'guardian_approved_at', 'updated_at'])
            messages.success(request, 'You approved the contact request. The scout can only see contact details the player has chosen to share.')
        elif request.POST.get('decision') == 'decline':
            contact_request.status = 'declined'
            contact_request.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'You declined the contact request. No contact details were shared.')
        else:
            messages.error(request, 'Choose whether to approve or decline.')
        return redirect('home')
    return render(
        request,
        'players/guardian_contact_review.html',
        {'contact_request': contact_request},
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
