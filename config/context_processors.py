from django.conf import settings


GOATCOUNTER_EXCLUDED_URL_NAMES = {
    'guardian_review',
    'guardian_contact_review',
    'updates_unsubscribe',
}


def goatcounter(request):
    resolver_match = getattr(request, 'resolver_match', None)
    return {
        'goatcounter_site_code': settings.GOATCOUNTER_SITE_CODE,
        'goatcounter_exclude_page': bool(
            resolver_match and resolver_match.url_name in GOATCOUNTER_EXCLUDED_URL_NAMES
        ),
    }
