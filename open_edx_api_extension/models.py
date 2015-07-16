from django.conf import settings
from django.conf.urls import include, url
from django.core.urlresolvers import clear_url_caches

try:
    from importlib import import_module
except ImportError:  # python = 2.6
    from django.utils.importlib import import_module


def patch_root_urlconf():
    urlconf_module = import_module(settings.ROOT_URLCONF)
    urlconf_module.urlpatterns = [
        url(r'^api/course_user_result/', include('open_edx_api_extension.urls')),
    ] + urlconf_module.urlpatterns
    clear_url_caches()

patch_root_urlconf()
