from collections import Counter

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
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
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from scouts.forms import ScoutOnboardingForm
from scouts.models import Scout

REPORTLAB_AVAILABLE = True

from .forms import AdminUserUpdateForm, RegistrationForm, LoginForm, OTPVerifyForm
from .models import User, OneTimeCode

logger = logging.getLogger(__name__)

def _is_staff_user(user):
    return user.is_authenticated and user.is_staff

def home(request):
    return render(request, 'users/home.html')


def send_otp_to_user(user, method='email'):
    # generate 6-digit code
    code = f"{random.randint(0, 999999):06d}"
    expires = timezone.now() + timedelta(minutes=15)
    OneTimeCode.objects.create(user=user, code=code, method=method, expires_at=expires)

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
        messages.error(request, 'No pending verification found. Please register or request a new code.')
        return redirect('register')

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
    user = User.objects.filter(id=pending_user_id).first() if pending_user_id else None
    if not user:
        messages.error(request, 'No pending verification found. Please register again.')
        return redirect('register')

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
                        'age': form.cleaned_data['age'],
                        'position': form.cleaned_data['position'],
                        'secondary_position': form.cleaned_data.get('secondary_position', ''),
                        'height_cm': form.cleaned_data.get('height_cm'),
                        'weight_kg': form.cleaned_data.get('weight_kg'),
                        'current_club': form.cleaned_data.get('current_club', ''),
                        'location': form.cleaned_data['location'],
                        'football_experience': form.cleaned_data.get('football_experience', ''),
                        'special_traits': form.cleaned_data.get('special_traits', ''),
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
    scouts = Scout.objects.select_related('user').all().order_by('verified', 'organization')
    return render(
        request,
        'users/admin_verifications.html',
        {'scouts': scouts},
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
    users = User.objects.all().order_by('full_name')

    if role_filter in {'player', 'scout'}:
        users = users.filter(role=role_filter)

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
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        if export_format == 'pdf':
            if not REPORTLAB_AVAILABLE:
                messages.error(request, 'PDF export is unavailable because reportlab is not installed in the active environment.')
                return redirect('admin_reports')

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, title=f'{report_type.title()} Report')
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph('Talanta FC Admin Report', styles['Title']))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f'Report Type: {report_type.title()}', styles['Heading2']))
            story.append(Paragraph(f'Filters: start date {start_date or "all"}, end date {end_date or "all"}, position {position_value or "all"}', styles['BodyText']))
            story.append(Spacer(1, 12))

            data = [report_headers] + report_rows
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
                if chart_type == 'pie':
                    total_value = sum(chart_values)
                    percent_labels = [
                        f'{label} ({(value / total_value * 100):.0f}%)' if total_value else label
                        for label, value in zip(chart_labels, chart_values)
                    ]
                    pie_chart = Pie()
                    pie_chart.width = 1.6 * inch
                    pie_chart.height = 1.6 * inch
                    pie_chart.data = chart_values
                    pie_chart.labels = percent_labels
                    pie_chart.slices.strokeColor = colors.white
                    pie_chart.slices.strokeWidth = 0.5
                    drawing = Drawing(240, 220)
                    drawing.add(pie_chart)
                    story.append(drawing)
                else:
                    bar_chart = VerticalBarChart()
                    bar_chart.width = 3.2 * inch
                    bar_chart.height = 2.2 * inch
                    bar_chart.x = 0.5 * inch
                    bar_chart.y = 0.2 * inch
                    bar_chart.data = [chart_values]
                    bar_chart.categoryAxis.categoryNames = chart_labels
                    bar_chart.valueAxis.valueMin = 0
                    bar_chart.valueAxis.valueMax = max(chart_values) + 1 if chart_values else 1
                    bar_chart.bars[0].fillColor = colors.HexColor('#198754')
                    drawing = Drawing(320, 220)
                    drawing.add(bar_chart)
                    story.append(drawing)
            doc.build(story)
            pdf_value = buffer.getvalue()
            response = HttpResponse(pdf_value, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timestamp}.pdf"'
            return response

        response = HttpResponse(content_type='text/csv')
        writer = csv.writer(response)
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timestamp}.csv"'
        writer.writerow(report_headers)
        for row in report_rows:
            writer.writerow(row)
        writer.writerow([])
        writer.writerow(['Chart Type', chart_type.title()])
        writer.writerow(['Chart Labels', '|'.join(chart_labels)])
        writer.writerow(['Chart Values', '|'.join(str(value) for value in chart_values)])
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