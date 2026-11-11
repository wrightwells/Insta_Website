class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        nonce = getattr(response, 'structured_data_nonce', '')
        script_sources = "'self'" + (" 'nonce-" + nonce + "'" if nonce else '')
        image_sources = "'self'" + ''.join(' ' + origin for origin in getattr(response, 'icon_origins', []))
        frames = "'self'" if getattr(response, "owner_preview", False) else "'none'"
        frame_src = "'none'"
        response["Content-Security-Policy"] = (
            f"default-src 'self'; script-src {script_sources}; style-src 'self'; "
            f"img-src {image_sources}; media-src 'self'; object-src 'none'; "
            f"frame-src {frame_src}; base-uri 'self'; frame-ancestors {frames}; form-action 'self'"
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Content and gated media must disappear on the next request after hiding.
        if not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store"
        response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
