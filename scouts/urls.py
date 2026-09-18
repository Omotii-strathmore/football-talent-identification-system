from django.urls import path
from . import views

urlpatterns = [

    path(
        'dashboard/',
        views.dashboard,
        name='scout_dashboard'
    ),
    path('players/', views.player_directory, name='scout_player_directory'),
    path('players/shortlist/toggle/', views.scout_toggle_shortlist, name='scout_toggle_shortlist'),
    path('players/interests/', views.scout_shortlist, name='scout_shortlist'),
    path('player-recommendations/', views.player_recommendations, name='scout_player_recommendations'),
    path('details/edit/', views.edit_details, name='scout_edit_details'),

]