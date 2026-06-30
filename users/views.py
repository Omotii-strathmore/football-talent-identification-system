from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

import csv

from opportunities.models import Application, Opportunity
from players.models import PlayerProfile, PlayerVideo
from players.forms import PlayerOnboardingForm
from scouts.forms import ScoutOnboardingForm
from scouts.models import Scout
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
            return redirect('complete_profile')

    else:

        form = RegistrationForm()

    return render(
        request,
        'users/register.html',
        {
            'form': form,
            'current_step': 1,
            'total_steps': 2,
            'step_title': 'Step 1 of 2: Account details',
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
        template_title = 'Step 2 of 2: Player profile'
    else:
        form_class = ScoutOnboardingForm
        template_title = 'Step 2 of 2: Scout profile'

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
            login(request, user)

            if user.role == 'player':
                messages.success(request, 'Registration complete. Welcome to your player dashboard.')
                return redirect('player_dashboard')

            messages.success(request, 'Registration complete. Your scout account is pending verification.')
            return redirect('scout_dashboard')
    else:
        form = form_class()

    return render(
        request,
        'users/complete_profile.html',
        {
            'form': form,
            'role': user.role,
            'current_step': 2,
            'total_steps': 2,
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


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_reports_view(request):

    report_type = request.GET.get('report', '').strip().lower()
    if report_type:
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        response = HttpResponse(content_type='text/csv')
        writer = csv.writer(response)

        if report_type == 'summary':
            response['Content-Disposition'] = f'attachment; filename="system_summary_report_{timestamp}.csv"'
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Player Profiles', PlayerProfile.objects.count()])
            writer.writerow(['Scout Profiles', Scout.objects.count()])
            writer.writerow(['Verified Scouts', Scout.objects.filter(verified=True).count()])
            writer.writerow(['Unverified Scouts', Scout.objects.filter(verified=False).count()])
            writer.writerow(['Total Opportunities', Opportunity.objects.count()])
            writer.writerow(['Active Opportunities', Opportunity.objects.filter(is_active=True).count()])
            writer.writerow(['Total Applications', Application.objects.count()])
            writer.writerow(['Uploaded Player Videos', PlayerVideo.objects.count()])
            return response

        if report_type == 'users':
            response['Content-Disposition'] = f'attachment; filename="users_report_{timestamp}.csv"'
            writer.writerow(['ID', 'Full Name', 'Email', 'Role', 'Is Staff', 'Is Active'])
            for user in User.objects.all().order_by('id'):
                writer.writerow([
                    user.id,
                    user.full_name,
                    user.email,
                    user.role,
                    user.is_staff,
                    user.is_active,
                ])
            return response

        if report_type == 'scouts':
            response['Content-Disposition'] = f'attachment; filename="scouts_report_{timestamp}.csv"'
            writer.writerow(['Scout ID', 'Name', 'Email', 'Organization', 'Specialization', 'Verified'])
            for scout in Scout.objects.select_related('user').all().order_by('id'):
                writer.writerow([
                    scout.id,
                    scout.user.full_name,
                    scout.user.email,
                    scout.organization,
                    scout.specialization,
                    scout.verified,
                ])
            return response

        if report_type == 'opportunities':
            response['Content-Disposition'] = f'attachment; filename="opportunities_report_{timestamp}.csv"'
            writer.writerow([
                'Opportunity ID',
                'Title',
                'Organization',
                'Location',
                'Deadline',
                'Active',
                'Max Applications',
                'Applications Count',
                'Scout Name',
                'Scout Email',
            ])
            queryset = Opportunity.objects.select_related('scout').all().order_by('id')
            for opportunity in queryset:
                writer.writerow([
                    opportunity.id,
                    opportunity.title,
                    opportunity.organization,
                    opportunity.location,
                    opportunity.deadline,
                    opportunity.is_active,
                    opportunity.max_applications,
                    opportunity.applications.count(),
                    opportunity.scout.full_name,
                    opportunity.scout.email,
                ])
            return response

        if report_type == 'applications':
            response['Content-Disposition'] = f'attachment; filename="applications_report_{timestamp}.csv"'
            writer.writerow([
                'Application ID',
                'Opportunity Title',
                'Player Name',
                'Player Email',
                'Status',
                'Applied At',
            ])
            queryset = Application.objects.select_related('opportunity', 'player').all().order_by('id')
            for application in queryset:
                writer.writerow([
                    application.id,
                    application.opportunity.title,
                    application.player.full_name,
                    application.player.email,
                    application.status,
                    timezone.localtime(application.applied_at).strftime('%Y-%m-%d %H:%M:%S'),
                ])
            return response

        if report_type == 'diagram_based':
            response['Content-Disposition'] = f'attachment; filename="kweyu_drnjeri_diagram_based_report_{timestamp}.csv"'
            writer.writerow([
                'Diagram Section',
                'Actor/Module',
                'Input',
                'Process',
                'Output',
                'Metric Value',
            ])

            # Conceptual/use-case aligned actor flows from the project document.
            writer.writerow([
                'Actor Flow',
                'Player',
                'Registration/Profile Data',
                'Create and maintain player profile',
                'Scouting-ready player profiles',
                PlayerProfile.objects.count(),
            ])
            writer.writerow([
                'Actor Flow',
                'Player',
                'Performance Videos',
                'Upload and manage video evidence',
                'Player videos visible to scouts',
                PlayerVideo.objects.count(),
            ])
            writer.writerow([
                'Actor Flow',
                'Player',
                'Opportunity Application Data',
                'Apply to trials/tournaments',
                'Submitted applications',
                Application.objects.count(),
            ])

            writer.writerow([
                'Actor Flow',
                'Scout/Coach',
                'Opportunity Details',
                'Post and manage opportunities',
                'Published opportunities',
                Opportunity.objects.count(),
            ])
            writer.writerow([
                'Actor Flow',
                'Scout/Coach',
                'Verification Documents',
                'Verification workflow and scouting access',
                'Verified scout accounts',
                Scout.objects.filter(verified=True).count(),
            ])

            writer.writerow([
                'Actor Flow',
                'Admin',
                'User and Verification Data',
                'Monitor system and approve/reject scouts',
                'Pending scout verifications',
                Scout.objects.filter(verified=False).count(),
            ])
            writer.writerow([
                'Actor Flow',
                'Admin',
                'System Operational Data',
                'Generate decision-support reports',
                'Total platform users',
                User.objects.count(),
            ])

            writer.writerow([
                'System Output',
                'Reporting',
                'Player + Scout + Opportunity + Application Data',
                'Aggregate and analyze by module',
                'Decision-support report entries',
                (
                    PlayerProfile.objects.count()
                    + Scout.objects.count()
                    + Opportunity.objects.count()
                    + Application.objects.count()
                ),
            ])
            return response

        messages.error(request, 'Invalid report type selected.')
        return redirect('admin_reports')

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

    return render(
        request,
        'users/admin_reports.html',
        {'reports': reports},
    )