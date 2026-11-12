from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',views.dashboard,name='player_dashboard'),
    path('community/', views.player_community, name='player_community'),
    path('journey/update/', views.journey_update, name='player_journey_update'),
    path('contact-requests/<int:request_id>/respond/', views.respond_to_contact_request, name='player_contact_request_respond'),
    path('guardian/contact-request/<str:token>/', views.guardian_contact_review, name='guardian_contact_review'),
    path('profile/', views.profile_view, name='player_profile'),
    path('category/', views.set_category, name='player_set_category'),
    path('videos/upload/', views.upload_video, name='upload_video'),
    path('videos/<int:video_id>/delete/', views.delete_video, name='delete_video'),
    path('guardian/resend/', views.guardian_resend, name='guardian_resend'),
    path('guardian/<str:token>/', views.guardian_review, name='guardian_review'),
]