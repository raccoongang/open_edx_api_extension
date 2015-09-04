from django.conf.urls import url
from django.conf import settings

from open_edx_api_extension import views


urlpatterns = [
    url(r'^courses/$', views.CourseList.as_view()),
    url(r'^courses/{}/(?P<username>\w+)/$'.format(settings.COURSE_ID_PATTERN), views.CourseUserResult.as_view()),
    url(r'^enrollment$', views.SSOEnrollmentListView.as_view(), name='courseenrollments'),
]
