from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SiteFeedback, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
	model = User
	list_display = ('email', 'full_name', 'role', 'is_staff')
	list_filter = ('role', 'is_staff', 'is_active')
	search_fields = ('email', 'full_name')
	ordering = ('email',)
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal info', {'fields': ('full_name', 'role')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
	)
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
		}),
	)


@admin.register(SiteFeedback)
class SiteFeedbackAdmin(admin.ModelAdmin):
	list_display = ('user', 'role', 'rating', 'created_at')
	list_filter = ('rating', 'role')
	search_fields = ('user__email', 'comment')
