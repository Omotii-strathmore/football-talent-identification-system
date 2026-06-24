from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect

from opportunities.models import Application, Opportunity
from players.models import PlayerProfile, PlayerVideo
from players.forms import PlayerOnboardingForm
from scouts.forms import ScoutOnboardingForm
from scouts.models import Scout
from .forms import AdminUserCreateForm, AdminUserUpdateForm, RegistrationForm, LoginForm
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

    create_form = AdminUserCreateForm()
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
            'create_form': create_form,
            'edit_form': edit_form,
            'edit_user': edit_user,
        },
    )


@login_required
@user_passes_test(_is_staff_user, login_url='login')
def admin_create_user_view(request):
    if request.method != 'POST':
        return redirect('admin_users')

    form = AdminUserCreateForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'User created successfully.')
        return redirect('admin_users')

    users = User.objects.all().order_by('full_name')
    return render(
        request,
        'users/admin_users.html',
        {
            'users': users,
            'create_form': form,
            'edit_form': None,
            'edit_user': None,
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
            'create_form': AdminUserCreateForm(),
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