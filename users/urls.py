from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
    path('feedback/', views.submit_feedback_view, name='submit_feedback'),

    path('register/', views.register_view, name='register'),
    path('register/check-email/', views.check_email_view, name='check_email'),
    path('account/photo-position/', views.photo_position_view, name='photo_position'),
    path('management/notifications/<int:notification_id>/', views.admin_notification_open, name='admin_notification_open'),
    path('management/notifications/read-all/', views.admin_notifications_read_all, name='admin_notifications_read_all'),
    path('account/email/', views.account_email_view, name='account_email'),
    path('ai/assist/', views.ai_assist_view, name='ai_assist'),

    path('register/complete-profile/', views.complete_profile_view, name='complete_profile'),

    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),

    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('verify-otp/resend/', views.resend_otp_view, name='resend_otp'),
    path('verify-otp/request/', views.resend_verification_request_view, name='resend_verification_request'),

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
    path('management/feedback/', views.admin_feedback_view, name='admin_feedback'),
    path('management/updates/', views.admin_updates_view, name='admin_updates'),
    path('management/backup/', views.admin_backup_view, name='admin_backup'),
    path('management/updates/ai-draft/', views.admin_update_ai_draft_view, name='admin_update_ai_draft'),
    path('management/updates/<int:update_id>/send/', views.admin_update_send_one_view, name='admin_update_send_one'),
    path('updates/feed/', views.updates_feed_view, name='updates_feed'),
    path('updates/<int:update_id>/seen/', views.update_seen_view, name='update_seen'),
    path('about/', views.about_view, name='about'),
    path('updates/<int:update_id>/email-me/', views.update_email_me_view, name='update_email_me'),
    path('updates/unsubscribe/<str:token>/', views.updates_unsubscribe_view, name='updates_unsubscribe'),
    path('management/reports/', views.admin_reports_view, name='admin_reports'),
]