from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',views.dashboard,name='player_dashboard'),
    path('profile/', views.profile_view, name='player_profile'),
    path('videos/upload/', views.upload_video, name='upload_video'),
    
]