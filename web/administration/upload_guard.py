from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.db import DatabaseError
from django.http import HttpResponse
from django.urls import Resolver404, resolve

from domain.content.editing import require_owner
from domain.content.media import MAX_IMAGE_BYTES


class BoundedImageUploadHandler(FileUploadHandler):
    """Abort multipart uploads before unbounded temporary files are written."""

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > MAX_IMAGE_BYTES:
            self.request.upload_rejected = True
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class UploadGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.content_type == "multipart/form-data":
            try:
                upload_route = resolve(request.path_info).url_name in {"owner_item_image", "owner_theme"}
            except Resolver404:
                upload_route = False
            if upload_route:
                try:
                    require_owner(request.user)
                except PermissionDenied:
                    return HttpResponse(_("Owner access required."), status=403)
                except DatabaseError:
                    return HttpResponse(_("Temporarily unavailable."), status=503)
                try:
                    content_length = int(request.META.get("CONTENT_LENGTH", 0))
                except (ValueError, TypeError):
                    content_length = 0
                if content_length > MAX_IMAGE_BYTES + 64 * 1024:
                    return HttpResponse(_("Upload exceeds the image limit."), status=413)
                # Parse while guarded, before CSRF/form processing. No domain
                # writes occur here; normal CSRF checks still run afterwards.
                _parsed_post = request.POST
                if getattr(request, "upload_rejected", False):
                    return HttpResponse(_("Upload exceeds the image limit."), status=413)
        return self.get_response(request)
