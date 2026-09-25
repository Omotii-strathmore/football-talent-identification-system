from collections import Counter

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging
import random

import csv
from io import BytesIO

from opportunities.models import Application, Opportunity
from players.models import PlayerProfile, PlayerVideo
from players.forms import PlayerOnboardingForm
from scouts.forms import ScoutOnboardingForm
from scouts.models import Scout

try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from .forms import (
    AdminUserUpdateForm,
    RegistrationForm,
    LoginForm,
    OTPVerifyForm,
    PasswordResetRequestForm,
    PasswordResetConfirmForm,
)
from .models import User, OneTimeCode

logger = logging.getLogger(__name__)

def _is_staff_user(user):
    return user.is_authenticated and user.is_staff

def home(request):
    return render(request, 'users/home.html')


def send_otp_to_user(user, method='email', purpose='verify'):
    # generate 6-digit code
    code = f"{random.randint(0, 999999):06d}"
    expires = timezone.now() + timedelta(minutes=15)
    OneTimeCode.objects.create(user=user, code=code, method=method, purpose=purpose, expires_at=expires)

    if purpose == 'reset':
        subject = 'Talanta Soka password reset code'
        message = (
            f'Hello {user.full_name},\n\n'
            f'Your Talanta Soka password reset code is: {code}\n'
            'It expires in 15 minutes.\n\n'
            'If you did not request a password reset, please ignore this email.'
        )
    else:
        subject = 'Talanta Soka verification code'
        message = (
            f'Hello {user.full_name},\n\n'
            f'Your Talanta Soka verification code is: {code}\n'
            'It expires in 15 minutes.\n\n'
            'If you did not request this, please ignore this email.'
        )
    sender_address = None
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend' and settings.EMAIL_HOST_USER:
        sender_address = settings.EMAIL_HOST_USER
    sender_address = sender_address or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'otp@talantasoka.com'
    from_email = f"{getattr(settings, 'EMAIL_FROM_NAME', 'Talanta Soka')} <{sender_address}>"

    if method == 'email':
        if not user.email:
            logger.warning('OTP email not sent because user has no email address: %s', user)
            return False
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend' and not settings.EMAIL_HOST_USER:
            logger.warning('SMTP EMAIL_HOST_USER is not configured; cannot send OTP email.')
            return False
        try:
            send_mail(subject, message, from_email, [user.email], fail_silently=False)
            logger.info('OTP email sent to %s using backend %s', user.email, settings.EMAIL_BACKEND)
            return True
        except Exception:
            logger.exception('Failed to send OTP email to %s', user.email)
            return False

    if method == 'sms':
        try:
            from twilio.rest import Client
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            twilio_number = getattr(settings, 'TWILIO_FROM_NUMBER', None)
            if account_sid and auth_token and twilio_number and getattr(user, 'contact_phone', None):
                client = Client(account_sid, auth_token)
                client.messages.create(body=message, from_=twilio_number, to=user.contact_phone)
                return True
            logger.warning('Twilio settings incomplete or user has no phone for SMS OTP: %s', user)
            return False
        except Exception as exc:
            logger.exception('Failed to send OTP SMS to %s', user)
            return False

    logger.warning('Unsupported OTP delivery method requested: %s', method)
    return False


def verify_otp_view(request):
    pending_user_id = request.session.get('pending_user_id')
    pending_user_email = request.session.get('pending_user_email')
    user = None

    if pending_user_id:
        user = User.objects.filter(id=pending_user_id).first()
    elif pending_user_email:
        user = User.objects.filter(email=pending_user_email, is_active=False).first()

    if not user:
        messages.error(request, 'No pending verification found. Please request a new code below.')
        return redirect('resend_verification_request')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = OneTimeCode.objects.filter(user=user, code=code, used=False).order_by('-created_at').first()
            if not otp:
                messages.error(request, 'Invalid verification code.')
            else:
                if otp.expires_at and otp.expires_at < timezone.now():
                    messages.error(request, 'Verification code has expired. Request a new one.')
                else:
                    otp.used = True
                    otp.save(update_fields=['used'])
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                    # clear pending id
                    request.session.pop('pending_user_id', None)
                    messages.success(request, 'Your account is verified. You may now sign in.')
                    return redirect('login')
    else:
        form = OTPVerifyForm()

    return render(request, 'users/verify_otp.html', {'form': form, 'user_email': user.email})


def resend_otp_view(request):
    pending_user_id = request.session.get('pending_user_id')
    pending_user_email = request.session.get('pending_user_email')
    user = None

    if pending_user_id:
        user = User.objects.filter(id=pending_user_id).first()
    elif pending_user_email:
        user = User.objects.filter(email=pending_user_email, is_active=False).first()

    if not user:
        messages.error(request, 'No pending verification found. Please request a new code below.')
        return redirect('resend_verification_request')

    method = request.POST.get('method', 'email')
    # create and send a fresh OTP
    success = send_otp_to_user(user, method=method)
    if success:
        messages.success(request, f'A new verification code was sent via {method}.')
        if method == 'email' and settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            messages.info(request, 'DEBUG mode: OTP is printed to the server console because SMTP is not configured.')
    else:
        if method == 'email':
            messages.error(request, 'Unable to send verification code via email. Please verify SMTP settings and make sure the sender address is allowed by your provider.')

    return redirect('verify_otp')


def resend_verification_request_view(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email, is_active=False).first()
            if user:
                request.session['pending_user_id'] = user.id
                request.session['pending_user_email'] = user.email
                sent = send_otp_to_user(user, method='email')
                if sent:
                    messages.success(request, 'A verification code was sent to your email.')
                    if settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                        messages.info(request, 'DEBUG mode: OTP is printed to the server console because SMTP is not configured.')
                    return redirect('verify_otp')
                messages.error(request, 'Unable to send the verification code via email. Please verify SMTP settings and try again.')
            else:
                # Do not reveal whether the email exists or is already verified.
                messages.success(request, 'If that email has a pending account, a verification code was sent to it.')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'users/resend_verification_request.html', {'form': form})


def password_reset_request_view(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email).first()
            if user:
                request.session['reset_user_id'] = user.id
                sent = send_otp_to_user(user, method='email', purpose='reset')
                if sent:
                    messages.success(request, 'A password reset code was sent to your email.')
                    if settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                        messages.info(request, 'DEBUG mode: OTP is printed to the server console because SMTP is not configured.')
                    return redirect('password_reset_confirm')
                messages.error(request, 'Unable to send the reset code via email. Please verify SMTP settings and try again.')
            else:
                # Do not reveal whether the email exists.
                messages.success(request, 'If that email is registered, a password reset code was sent to it.')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'users/password_reset_request.html', {'form': form})


def password_reset_confirm_view(request):
    reset_user_id = request.session.get('reset_user_id')
    user = User.objects.filter(id=reset_user_id).first() if reset_user_id else None

    if not user:
        messages.error(request, 'No pending password reset found. Please request a new code.')
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = PasswordResetConfirmForm(request.POST, user=user)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = OneTimeCode.objects.filter(user=user, code=code, purpose='reset', used=False).order_by('-created_at').first()
            if not otp:
                messages.error(request, 'Invalid verification code.')
            elif otp.expires_at and otp.expires_at < timezone.now():
                messages.error(request, 'Verification code has expired. Request a new one.')
            else:
                otp.used = True
                otp.save(update_fields=['used'])
                user.set_password(form.cleaned_data['new_password'])
                user.save(update_fields=['password'])
                request.session.pop('reset_user_id', None)
                messages.success(request, 'Your password has been reset. You may now sign in.')
                return redirect('login')
    else:
        form = PasswordResetConfirmForm()

    return render(request, 'users/password_reset_confirm.html', {'form': form, 'user_email': user.email})


def password_reset_resend_view(request):
    reset_user_id = request.session.get('reset_user_id')
    user = User.objects.filter(id=reset_user_id).first() if reset_user_id else None
    if not user:
        messages.error(request, 'No pending password reset found. Please request a new code.')
        return redirect('password_reset_request')

    sent = send_otp_to_user(user, method='email', purpose='reset')
    if sent:
        messages.success(request, 'A new password reset code was sent to your email.')
    else:
        messages.error(request, 'Unable to send the reset code via email. Please verify SMTP settings and try again.')

    return redirect('password_reset_confirm')


def register_view(request):

    if request.method == 'POST':

        form = RegistrationForm(request.POST)

        if form.is_valid():

            user = form.save()
            # mark user inactive until verified
            user.is_active = False
            user.save(update_fields=['is_active'])

            request.session['pending_user_id'] = user.id
            request.session['pending_user_email'] = user.email
            messages.success(request, 'Registration successful. Please complete your role profile in step 2.')
            return redirect('complete_profile')

    else:

        form = RegistrationForm()

    return render(
        request,
        'users/register.html',
        {
            'form': form,
            'current_step': 1,
            'total_steps': 3,
            'step_title': 'Step 1 of 3: Basic registration',
        }
    )


def complete_profile_view(request):
    pending_user_id = request.session.get('pending_user_id')

    if not pending_user_id:
        messages.info(request, 'Start from registration to complete profile details.')
        return redirect('register')

    user = User.objects.filter(id=pending_user_id).first()

    if not user:
        request.session.pop('pending_user_id', None)
        messages.error(request, 'Could not find your account. Please register again.')
        return redirect('register')

    if user.role == 'player':
        form_class = PlayerOnboardingForm
        template_title = 'Step 2 of 3: Player profile'
    else:
        form_class = ScoutOnboardingForm
        template_title = 'Step 2 of 3: Scout profile'

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)

        if form.is_valid():
            if user.role == 'player':
                PlayerProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'full_name': user.full_name,
                        'date_of_birth': form.cleaned_data['date_of_birth'],
                        'position': form.cleaned_data['position'],
                        'location': form.cleaned_data['location'],
                    }
                )
            else:
                Scout.objects.update_or_create(
                    user=user,
                    defaults={
                        'organization': form.cleaned_data['organization'],
                        'specialization': form.cleaned_data['specialization'],
                        'verification_document': form.cleaned_data['verification_document'],
                        'profile_photo': form.cleaned_data.get('profile_photo'),
                    }
                )

            request.session['pending_user_id'] = user.id
            request.session['pending_user_email'] = user.email
            # send OTP after role profile completion
            sent = send_otp_to_user(user, method='email')
            role_label = 'Player' if user.role == 'player' else 'Scout'
            if sent:
                messages.success(request, f'{role_label} profile completed successfully. A verification code was sent to your email.')
                if settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                    messages.info(request, 'DEBUG mode: OTP is printed to the server console because SMTP is not configured.')
            else:
                messages.warning(request, f'{role_label} profile completed successfully, but we could not send the verification email. Please verify your email settings and resend the code.')
            return redirect('verify_otp')
    else:
        form = form_class()

    return render(
        request,
        'users/complete_profile.html',
        {
            'form': form,
            'role': user.role,
            'current_step': 2,
            'total_steps': 3,
            'step_title': template_title,
            'kenya_counties': PlayerOnboardingForm.KENYA_COUNTIES if user.role == 'player' else [],
        }
    )


def login_view(request):

    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            user = authenticate(
                request,
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )

            if user:

                if user.is_staff:
                    login(request, user)
                    return redirect('admin_dashboard')

                # Ensure role-specific profile exists before allowing dashboard access.
                if user.role == 'player' and not hasattr(user, 'player_profile'):
                    request.session['pending_user_id'] = user.id
                    messages.info(request, 'Complete your player profile before continuing.')
                    return redirect('complete_profile')

                if user.role == 'scout' and not hasattr(user, 'scout_profile'):
                    request.session['pending_user_id'] = user.id
                    messages.info(request, 'Complete your scout profile before continuing.')
                    return redirect('complete_profile')

                login(request, user)
                messages.success(request, 'Login successful. Welcome back!')

                if user.role == 'player':
                    return redirect('player_dashboard')

                return redirect('scout_dashboard')

            # If authentication failed, check for an inactive user with valid credentials.
            inactive_user = User.objects.filter(email=form.cleaned_data['email'], is_active=False).first()
            if inactive_user and inactive_user.check_password(form.cleaned_data['password']):
                request.session['pending_user_id'] = inactive_user.id
                request.session['pending_user_email'] = inactive_user.email
                messages.info(request, 'Your account is not yet verified. Please enter the code sent to your email.')
                return redirect('verify_otp')

            messages.error(request, 'Invalid email or password.')

    else:

        form = LoginForm()

    return render(
        request,
        'users/login.html',
        {
            'form': form,
        }
    )


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_dashboard_view(request):
    first_name = (request.user.full_name or 'Admin').split()[0]
    total_users = User.objects.count()
    total_players = User.objects.filter(role='player').count()
    total_scouts = User.objects.filter(role='scout').count()
    pending_verifications = Scout.objects.filter(verification_status='pending').count()
    opportunities_count = Opportunity.objects.count()
    applications_count = Application.objects.count()

    return render(
        request,
        'users/admin_dashboard.html',
        {
            'first_name': first_name,
            'total_users': total_users,
            'total_players': total_players,
            'total_scouts': total_scouts,
            'pending_verifications': pending_verifications,
            'opportunities_count': opportunities_count,
            'applications_count': applications_count,
        },
    )


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_verifications_view(request):
    all_scouts = Scout.objects.select_related('user').all()
    status_counts = {
        'pending': all_scouts.filter(verification_status='pending').count(),
        'approved': all_scouts.filter(verification_status='approved').count(),
        'rejected': all_scouts.filter(verification_status='rejected').count(),
    }

    status_filter = request.GET.get('status', '').strip().lower()
    scouts = all_scouts
    if status_filter in {'pending', 'approved', 'rejected'}:
        scouts = scouts.filter(verification_status=status_filter)

    scouts = scouts.order_by('verified', 'organization')

    return render(
        request,
        'users/admin_verifications.html',
        {
            'scouts': scouts,
            'status_filter': status_filter,
            'status_counts': status_counts,
            'total_scouts': all_scouts.count(),
        },
    )


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_approve_scout_view(request, scout_id):
    if request.method != 'POST':
        return redirect('admin_verifications')

    scout = get_object_or_404(Scout, id=scout_id)
    scout.verified = True
    scout.verification_status = 'approved'
    scout.save(update_fields=['verified', 'verification_status'])
    messages.success(request, f'Scout {scout.user.full_name} has been approved.')
    return redirect('admin_verifications')


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_reject_scout_view(request, scout_id):
    if request.method != 'POST':
        return redirect('admin_verifications')

    scout = get_object_or_404(Scout, id=scout_id)
    scout.verified = False
    scout.verification_status = 'rejected'
    scout.save(update_fields=['verified', 'verification_status'])
    messages.info(request, f'Scout {scout.user.full_name} has been rejected.')
    return redirect('admin_verifications')


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_users_view(request):
    role_filter = request.GET.get('role', '').strip().lower()
    search_query = request.GET.get('q', '').strip()
    all_users = User.objects.all()
    role_counts = {
        'player': all_users.filter(role='player').count(),
        'scout': all_users.filter(role='scout').count(),
        'staff': all_users.filter(is_staff=True).count(),
    }

    users = all_users.order_by('full_name')

    if role_filter == 'staff':
        users = users.filter(is_staff=True)
    elif role_filter in {'player', 'scout'}:
        users = users.filter(role=role_filter)

    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | Q(email__icontains=search_query)
        )

    edit_id = request.GET.get('edit')
    edit_user = None
    edit_form = None

    if edit_id:
        edit_user = User.objects.filter(id=edit_id).first()
        if edit_user:
            edit_form = AdminUserUpdateForm(instance=edit_user)

    return render(
        request,
        'users/admin_users.html',
        {
            'users': users,
            'role_filter': role_filter,
            'search_query': search_query,
            'role_counts': role_counts,
            'total_users': all_users.count(),
            'edit_form': edit_form,
            'edit_user': edit_user,
        },
    )


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_update_user_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    if request.method != 'POST':
        return redirect('admin_users')

    form = AdminUserUpdateForm(request.POST, instance=target_user)
    if form.is_valid():
        form.save()
        messages.success(request, 'User updated successfully.')
        return redirect('admin_users')

    users = User.objects.all().order_by('full_name')
    return render(
        request,
        'users/admin_users.html',
        {
            'users': users,
            'edit_form': form,
            'edit_user': target_user,
        },
    )


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_delete_user_view(request, user_id):
    if request.method != 'POST':
        return redirect('admin_users')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        messages.error(request, 'You cannot delete your own admin account.')
        return redirect('admin_users')

    target_user.delete()
    messages.success(request, 'User deleted successfully.')
    return redirect('admin_users')


def _normalize_position_filter(position_value):
    if not position_value or position_value == 'all':
        return None
    normalized = position_value.strip()
    if normalized.lower() == 'striker':
        return 'Forward'
    return normalized


def _get_filtered_player_queryset(start_date=None, end_date=None, position_value=None):
    queryset = PlayerProfile.objects.select_related('user').all()

    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)

    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)

    normalized_position = _normalize_position_filter(position_value)
    if normalized_position:
        queryset = queryset.filter(position=normalized_position)

    return queryset


def _build_chart_data_for_report(report_type, report_rows):
    if report_type == 'summary':
        chart_labels = [row[0] for row in report_rows if row]
        chart_values = [row[1] for row in report_rows if row and len(row) > 1]
        chart_title = 'Summary Metrics'
    elif report_type == 'players':
        position_counts = Counter(row[1] for row in report_rows if row and len(row) > 1)
        chart_labels = [label for label, _ in sorted(position_counts.items())]
        chart_values = [position_counts[label] for label in chart_labels]
        chart_title = 'Players by Position'
    elif report_type == 'users':
        role_counts = Counter(row[2] for row in report_rows if row and len(row) > 2)
        chart_labels = [label for label, _ in sorted(role_counts.items())]
        chart_values = [role_counts[label] for label in chart_labels]
        chart_title = 'Users by Role'
    elif report_type == 'scouts':
        verified_counts = Counter('Verified' if row[4] else 'Unverified' for row in report_rows if row and len(row) > 4)
        chart_labels = [label for label, _ in sorted(verified_counts.items())]
        chart_values = [verified_counts[label] for label in chart_labels]
        chart_title = 'Scouts by Verification'
    elif report_type == 'opportunities':
        status_counts = Counter('Active' if row[4] else 'Inactive' for row in report_rows if row and len(row) > 4)
        chart_labels = [label for label, _ in sorted(status_counts.items())]
        chart_values = [status_counts[label] for label in chart_labels]
        chart_title = 'Opportunities by Status'
    elif report_type == 'applications':
        status_counts = Counter(row[3] for row in report_rows if row and len(row) > 3)
        chart_labels = [label for label, _ in sorted(status_counts.items())]
        chart_values = [status_counts[label] for label in chart_labels]
        chart_title = 'Applications by Status'
    else:
        chart_labels = []
        chart_values = []
        chart_title = 'Report Overview'

    if not chart_labels and not chart_values:
        chart_labels = ['No data']
        chart_values = [0]

    return chart_labels, chart_values, chart_title


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_reports_view(request):
    report_type = request.GET.get('report', '').strip().lower()
    action = request.GET.get('action', 'preview').strip().lower()
    export_format = request.GET.get('format', 'csv').strip().lower()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    position_value = request.GET.get('position', 'all').strip()
    chart_type = request.GET.get('chart_type', 'bar').strip().lower()

    players_queryset = _get_filtered_player_queryset(start_date, end_date, position_value)

    report_headers = []
    report_rows = []

    if report_type == 'summary':
        report_headers = ['Metric', 'Value']
        report_rows = [
            ['Player Profiles', players_queryset.count()],
            ['Scout Profiles', Scout.objects.count()],
            ['Verified Scouts', Scout.objects.filter(verified=True).count()],
            ['Unverified Scouts', Scout.objects.filter(verified=False).count()],
            ['Total Opportunities', Opportunity.objects.count()],
            ['Active Opportunities', Opportunity.objects.filter(is_active=True).count()],
            ['Total Applications', Application.objects.count()],
            ['Uploaded Player Videos', PlayerVideo.objects.count()],
        ]
    elif report_type == 'players':
        report_headers = ['Player Name', 'Position', 'Location', 'Created At']
        report_rows = [
            [player.full_name, player.position, player.location, timezone.localtime(player.created_at).strftime('%Y-%m-%d')]
            for player in players_queryset.order_by('full_name')
        ]
    elif report_type == 'users':
        report_headers = ['Full Name', 'Email', 'Role', 'Is Staff', 'Is Active']
        report_rows = [
            [user.full_name, user.email, user.role, user.is_staff, user.is_active]
            for user in User.objects.all().order_by('full_name')
        ]
    elif report_type == 'scouts':
        report_headers = ['Name', 'Email', 'Organization', 'Specialization', 'Verified']
        report_rows = [
            [scout.user.full_name, scout.user.email, scout.organization, scout.specialization, scout.verified]
            for scout in Scout.objects.select_related('user').all().order_by('organization')
        ]
    elif report_type == 'opportunities':
        report_headers = ['Title', 'Organization', 'Location', 'Deadline', 'Active', 'Applications Count']
        report_rows = [
            [opportunity.title, opportunity.organization, opportunity.location, opportunity.deadline, opportunity.is_active, opportunity.applications.count()]
            for opportunity in Opportunity.objects.select_related('scout').all().order_by('title')
        ]
    elif report_type == 'applications':
        report_headers = ['Opportunity Title', 'Player Name', 'Player Email', 'Status', 'Applied At']
        report_rows = [
            [application.opportunity.title, application.player.full_name, application.player.email, application.status, timezone.localtime(application.applied_at).strftime('%Y-%m-%d %H:%M:%S')]
            for application in Application.objects.select_related('opportunity', 'player').all().order_by('id')
        ]

    chart_labels, chart_values, chart_title = _build_chart_data_for_report(report_type, report_rows)

    if report_type and action == 'generate':
        if not report_headers:
            messages.error(request, f'Unknown report type "{report_type}". Please choose a report from the list.')
            return redirect('admin_reports')

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        if export_format == 'pdf':
            if not REPORTLAB_AVAILABLE:
                messages.error(request, 'PDF export is unavailable because reportlab is not installed in the active environment.')
                return redirect('admin_reports')

            try:
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, title=f'{report_type.title()} Report')
                styles = getSampleStyleSheet()
                story = []
                story.append(Paragraph('Talanta FC Admin Report', styles['Title']))
                story.append(Spacer(1, 12))
                story.append(Paragraph(f'Report Type: {report_type.title()}', styles['Heading2']))
                story.append(Paragraph(f'Filters: start date {start_date or "all"}, end date {end_date or "all"}, position {position_value or "all"}', styles['BodyText']))
                story.append(Spacer(1, 12))

                safe_rows = [[str(cell) for cell in row] for row in report_rows]
                data = [report_headers] + safe_rows
                table = Table(data, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ]))
                story.append(table)
                story.append(Spacer(1, 12))
                story.append(Paragraph(f'Chart: {chart_type.title()} view', styles['Heading2']))
                if chart_labels and chart_values:
                    palette = [
                        colors.HexColor('#0d6efd'), colors.HexColor('#198754'), colors.HexColor('#fd7e14'),
                        colors.HexColor('#dc3545'), colors.HexColor('#6f42c1'), colors.HexColor('#20c997'),
                        colors.HexColor('#0dcaf0'), colors.HexColor('#d63384'), colors.HexColor('#ffc107'),
                        colors.HexColor('#6610f2'),
                    ]
                    if chart_type == 'pie':
                        total_value = sum(chart_values)
                        percent_labels = [
                            f'{(value / total_value * 100):.0f}%' if total_value else '0%'
                            for value in chart_values
                        ]
                        pie_chart = Pie()
                        pie_chart.x = 40
                        pie_chart.y = 30
                        pie_chart.width = 2.6 * inch
                        pie_chart.height = 2.6 * inch
                        pie_chart.data = chart_values
                        pie_chart.labels = percent_labels
                        pie_chart.slices.strokeColor = colors.white
                        pie_chart.slices.strokeWidth = 1
                        pie_chart.simpleLabels = 1
                        pie_chart.sideLabels = 0
                        for i in range(len(chart_values)):
                            pie_chart.slices[i].fillColor = palette[i % len(palette)]

                        legend = Legend()
                        legend.x = 4.6 * inch
                        legend.y = 2.6 * inch
                        legend.dx = 8
                        legend.dy = 8
                        legend.fontName = 'Helvetica'
                        legend.fontSize = 8
                        legend.boxAnchor = 'nw'
                        legend.columnMaximum = 12
                        legend.alignment = 'right'
                        legend.deltax = 8
                        legend.deltay = 10
                        legend.colorNamePairs = [
                            (palette[i % len(palette)], f'{label} ({chart_values[i]})')
                            for i, label in enumerate(chart_labels)
                        ]

                        drawing = Drawing(520, 300)
                        drawing.add(pie_chart)
                        drawing.add(legend)
                        story.append(drawing)
                    else:
                        bar_chart = VerticalBarChart()
                        bar_chart.width = 4.6 * inch
                        bar_chart.height = 2.8 * inch
                        bar_chart.x = 0.6 * inch
                        bar_chart.y = 0.9 * inch
                        bar_chart.data = [chart_values]
                        bar_chart.categoryAxis.categoryNames = chart_labels
                        bar_chart.categoryAxis.labels.fontSize = 7
                        bar_chart.categoryAxis.labels.angle = 30
                        bar_chart.categoryAxis.labels.dx = -6
                        bar_chart.categoryAxis.labels.dy = -12
                        bar_chart.categoryAxis.labels.boxAnchor = 'e'
                        bar_chart.valueAxis.valueMin = 0
                        bar_chart.valueAxis.valueMax = max(chart_values) + 1 if chart_values else 1
                        bar_chart.valueAxis.labels.fontSize = 8
                        bar_chart.barLabelFormat = '%d'
                        bar_chart.barLabels.nudge = 8
                        bar_chart.barLabels.fontSize = 8
                        bar_chart.barSpacing = 4
                        for i in range(len(chart_values)):
                            bar_chart.bars[(0, i)].fillColor = palette[i % len(palette)]
                        drawing = Drawing(520, 300)
                        drawing.add(bar_chart)
                        story.append(drawing)
                doc.build(story)
                pdf_value = buffer.getvalue()
            except Exception:
                logger.exception('Failed to build PDF report "%s"', report_type)
                messages.error(request, 'Could not generate the PDF report. Please try again, or export as CSV instead.')
                return redirect('admin_reports')

            response = HttpResponse(pdf_value, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timestamp}.pdf"'
            return response

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timestamp}.csv"'
        # UTF-8 BOM + explicit separator hint so Excel opens this correctly on any regional
        # locale, instead of mangling accented characters or splitting on the wrong delimiter.
        response.write('﻿')
        response.write('sep=,\r\n')
        writer = csv.writer(response)
        writer.writerow(report_headers)
        for row in report_rows:
            writer.writerow(row)
        return response

    reports = {
        'players_total': PlayerProfile.objects.count(),
        'scouts_total': Scout.objects.count(),
        'verified_scouts': Scout.objects.filter(verified=True).count(),
        'unverified_scouts': Scout.objects.filter(verified=False).count(),
        'opportunities_total': Opportunity.objects.count(),
        'active_opportunities': Opportunity.objects.filter(is_active=True).count(),
        'applications_total': Application.objects.count(),
        'videos_total': PlayerVideo.objects.count(),
    }

    preview_mode = 'chart' if action == 'chart' else 'preview'

    return render(
        request,
        'users/admin_reports.html',
        {
            'reports': reports,
            'report_type': report_type,
            'action': action,
            'preview_mode': preview_mode,
            'export_format': export_format,
            'start_date': start_date,
            'end_date': end_date,
            'position_filter': position_value,
            'chart_type': chart_type,
            'chart_title': chart_title,
            'chart_labels': chart_labels,
            'chart_values': chart_values,
            'report_headers': report_headers,
            'report_rows': report_rows,
        },
    )