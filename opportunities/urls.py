from django.urls import path

from . import views


urlpatterns = [
	path('', views.view_opportunities, name='view_opportunities'),
	path('apply/<int:opportunity_id>/', views.apply_opportunity, name='apply_opportunity'),
	path('applications/', views.my_applications, name='my_applications'),
	path('post/', views.post_opportunity, name='post_opportunity'),
	path('manage/', views.manage_posted_opportunities, name='manage_posted_opportunities'),
	path(
		'applications/<int:application_id>/status/<str:status>/',
		views.update_application_status,
		name='update_application_status',
	),
]
