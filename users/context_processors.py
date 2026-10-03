from urllib.parse import urlencode

from django.conf import settings

from .models import SiteFeedback, UpdateReceipt

# Options that only make sense for the other role.
ROLE_HIDDEN_REASONS = {
    'player': {'find_players'},
    'scout': {'videos'},
}


def site_extras(request):
    email = settings.SUPPORT_EMAIL
    compose_url = 'https://mail.google.com/mail/?' + urlencode({
        'view': 'cm',
        'fs': '1',
        'to': email,
        'su': 'Talanta Soka',
    })
    report_url = 'https://mail.google.com/mail/?' + urlencode({
        'view': 'cm', 'fs': '1', 'to': email, 'su': 'Talanta Soka - Report a concern',
        'body': 'Please tell us what happened, who was involved (name or trial), and when. We read every report.\n\n',
    })
    context = {'support_email': email, 'support_compose_url': compose_url, 'report_concern_url': report_url}
    # A label on every page when running on the laptop's practice database (demo accounts), never on the live site.
    from django.db import connection
    context['practice_mode'] = str(connection.settings_dict.get('NAME', '')).endswith('practice.sqlite3')
    # Public pages (the trials page) keep the landing-page header even for signed-in people.
    match = getattr(request, 'resolver_match', None)
    context['public_page'] = bool(match and match.url_name == 'public_opportunities')

    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_staff:
        from .models import AdminNotification
        context['admin_unread'] = AdminNotification.objects.filter(read_at__isnull=True).count()
    if user is not None and user.is_authenticated and not user.is_staff:
        # Show the newest update this person has not seen yet, once, as a pop-up on their pages.
        receipt = (UpdateReceipt.objects.filter(user=user, seen_at__isnull=True)
                   .select_related('update').order_by('-update__created_at').first())
        if receipt and request.GET.get('update') is None:
            context['pending_site_update'] = receipt.update
        ask = not SiteFeedback.objects.filter(user=user).exists()
        context['ask_site_feedback'] = ask
        if ask:
            hidden = ROLE_HIDDEN_REASONS.get(user.role, set())
            context['site_feedback_reasons'] = {
                rating: [{'code': code, 'label': label} for code, label in choices if code not in hidden]
                for rating, choices in SiteFeedback.REASON_CHOICES.items()
            }
    return context
