from urllib.parse import urlencode

from django.conf import settings

from .models import SiteFeedback

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
    context = {'support_email': email, 'support_compose_url': compose_url}

    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and not user.is_staff:
        ask = not SiteFeedback.objects.filter(user=user).exists()
        context['ask_site_feedback'] = ask
        if ask:
            hidden = ROLE_HIDDEN_REASONS.get(user.role, set())
            context['site_feedback_reasons'] = {
                rating: [{'code': code, 'label': label} for code, label in choices if code not in hidden]
                for rating, choices in SiteFeedback.REASON_CHOICES.items()
            }
    return context
