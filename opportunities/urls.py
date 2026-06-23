from django.urls import path

from . import views


urlpatterns = [
	path('', views.view_opportunities, name='view_opportunities'),
	path('apply/<int:opportunity_id>/', views.apply_opportunity, name='apply_opportunity'),
	path('applications/', views.my_applications, name='my_applications'),
	path('post/', views.post_opportunity, name='post_opportunity'),
]
