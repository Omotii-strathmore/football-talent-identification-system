from django.urls import path
from . import views

urlpatterns = [

    path(
        'dashboard/',
        views.dashboard,
        name='scout_dashboard'
    ),
    path('players/', views.player_directory, name='scout_player_directory'),

]