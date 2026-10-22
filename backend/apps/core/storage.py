from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateFileSystemStorage(FileSystemStorage):
    """Local storage for uploads that must never be reachable by a public URL.

    Files live outside the web root; they are served only through authenticated views
    (see apps.assignments.views) that check family membership first.
    """

    def __init__(self, location=None, **kwargs):
        kwargs.pop("base_url", None)
        super().__init__(location=location, base_url=None, **kwargs)

    def url(self, name):  # pragma: no cover - guard against accidental exposure
        raise ValueError("Private files have no public URL; serve them through an authenticated view.")
