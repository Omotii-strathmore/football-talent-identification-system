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
    context = {'support_email': email, 'support_compose_url': compose_url}

    user = getattr(request, 'user', None)
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
