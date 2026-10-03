from django.utils.cache import patch_cache_control

# Pages with sign-in or password forms. They must never be kept in the browser's history cache,
# otherwise pressing Back after logging out can bring back what was typed.
FORM_PAGE_PREFIXES = ('/login/', '/register/', '/verify-otp/', '/password-reset/')


class DisableClientCacheMiddleware:
    """Prevent browsers from storing authenticated pages and sign-in forms in history cache."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated or request.path.startswith(FORM_PAGE_PREFIXES):
            patch_cache_control(
                response,
                no_cache=True,
                no_store=True,
                must_revalidate=True,
                private=True,
                max_age=0,
            )
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response


class DailyTasksMiddleware:
    """Small daily jobs that would normally be scheduled, run on the first visit of the day."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            from opportunities.reminders import run_once_today
            run_once_today()
        except Exception:  # a reminder problem must never break a page
            import logging
            logging.getLogger(__name__).exception('Daily tasks failed')
        return response
