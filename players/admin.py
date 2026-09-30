from django.contrib import admin

from .models import PlayerProfile


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'age', 'position', 'location', 'guardian_status')
    list_filter = ('position',)
    search_fields = ('full_name', 'user__email', 'guardian_email')
    readonly_fields = ('guardian_consent_at', 'guardian_email_sent_at')

    @admin.display(description='Guardian approval')
    def guardian_status(self, obj):
        if not obj.is_minor:
            return 'Not needed (18+)'
        if obj.guardian_approved_at:
            return 'Approved'
        if obj.guardian_declined_at:
            return 'Declined'
        return 'Waiting'
