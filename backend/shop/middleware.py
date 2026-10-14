from django.conf import settings


def noindex_middleware(get_response):
    """Staging: tell search engines to stay away from every response (pages, API, files)."""

    def middleware(request):
        response = get_response(request)
        if settings.NOINDEX:
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    return middleware
