from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),

    path('register/', views.register_view, name='register'),

    path('register/complete-profile/', views.complete_profile_view, name='complete_profile'),

    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),

    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('verify-otp/resend/', views.resend_otp_view, name='resend_otp'),

    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password-reset/confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset/resend/', views.password_reset_resend_view, name='password_reset_resend'),

    path('management/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('management/verifications/', views.admin_verifications_view, name='admin_verifications'),
    path('management/verifications/<int:scout_id>/approve/', views.admin_approve_scout_view, name='admin_approve_scout'),
    path('management/verifications/<int:scout_id>/reject/', views.admin_reject_scout_view, name='admin_reject_scout'),
    path('management/users/', views.admin_users_view, name='admin_users'),
    path('management/users/<int:user_id>/update/', views.admin_update_user_view, name='admin_update_user'),
    path('management/users/<int:user_id>/delete/', views.admin_delete_user_view, name='admin_delete_user'),
    path('management/reports/', views.admin_reports_view, name='admin_reports'),
]