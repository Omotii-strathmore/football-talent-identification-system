from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),

    path('register/', views.register_view, name='register'),

    path('register/complete-profile/', views.complete_profile_view, name='complete_profile'),

    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),
]