from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

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

from .forms import AdminUserUpdateForm, RegistrationForm, LoginForm
from .models import User


def _is_staff_user(user):
    return user.is_authenticated and user.is_staff

def home(request):
    return render(request, 'users/home.html')


def register_view(request):

    if request.method == 'POST':

        form = RegistrationForm(request.POST)

        if form.is_valid():

            user = form.save()
            request.session['pending_user_id'] = user.id
            messages.success(request, 'User registration was successful. Please complete your profile in the next step.')
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

            request.session.pop('pending_user_id', None)
            role_label = 'Player' if user.role == 'player' else 'Scout'
            messages.success(request, f'{role_label} registration completed successfully. Please sign in to continue.')
            return redirect('login')
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
    pending_verifications = Scout.objects.filter(verified=False).count()
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
    scout.save(update_fields=['verified'])
    messages.success(request, f'Scout {scout.user.full_name} has been approved.')
    return redirect('admin_verifications')


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_reject_scout_view(request, scout_id):
    if request.method != 'POST':
        return redirect('admin_verifications')

    scout = get_object_or_404(Scout, id=scout_id)
    scout.verified = False
    scout.save(update_fields=['verified'])
    messages.info(request, f'Scout {scout.user.full_name} marked as not verified.')
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
    chart_queryset = players_queryset
    chart_data = list(chart_queryset.values('position').annotate(count=Count('id')).order_by('position'))
    if not chart_data:
        chart_data = [{'position': 'No data', 'count': 0}]

    chart_labels = [item['position'] for item in chart_data]
    chart_values = [item['count'] for item in chart_data]

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
                    pie_chart = Pie()
                    pie_chart.width = 2.2 * inch
                    pie_chart.height = 2.2 * inch
                    pie_chart.data = chart_values
                    pie_chart.labels = chart_labels
                    pie_chart.slices.strokeColor = colors.white
                    pie_chart.slices.strokeWidth = 0.5
                    drawing = Drawing(300, 220)
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
            'chart_title': 'Players by Position',
            'chart_labels': chart_labels,
            'chart_values': chart_values,
            'report_headers': report_headers,
            'report_rows': report_rows,
        },
    )