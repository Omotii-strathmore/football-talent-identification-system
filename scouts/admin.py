from django.contrib import admin

from .models import FairPlayAward


@admin.register(FairPlayAward)
class FairPlayAwardAdmin(admin.ModelAdmin):
    """The administrator can remove a Fair Play badge that was given unfairly."""
    list_display = ('profile', 'scout', 'qualities', 'created_at')
    search_fields = ('profile__full_name', 'scout__full_name', 'scout__email')
