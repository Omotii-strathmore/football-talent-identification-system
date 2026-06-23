from django.contrib import admin

from .models import Application, Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
	list_display = ('title', 'organization', 'location', 'deadline', 'is_active', 'created_at')
	list_filter = ('is_active', 'deadline', 'created_at')
	search_fields = ('title', 'organization', 'location', 'description')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
	list_display = ('opportunity', 'player', 'status', 'applied_at')
	list_filter = ('status', 'applied_at')
	search_fields = ('player__email', 'opportunity__title', 'opportunity__organization')
