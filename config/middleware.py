from django.utils.cache import patch_cache_control


class DisableClientCacheMiddleware:
    """Prevent browsers from storing authenticated pages in history cache."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
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
