from django.conf.urls import url
from django.conf import settings

from open_edx_api_extension import views


urlpatterns = [
    url(r'^courses/$', views.CourseList.as_view()),
    url(r'^courses/proctored$', views.CourseListWithExams.as_view()),
    url(r'^courses/{}/(?P<username>\w+)/$'.format(settings.COURSE_ID_PATTERN), views.CourseUserResult.as_view()),
    url(r'^enrollment$', views.SSOEnrollmentListView.as_view(), name='courseenrollments'),
    url(r'^user_proctored_exams/(?P<username>\w+)/$',
        views.ProctoredExamsListView.as_view(), name='user_proctored_exams'),
    url(r'^libraries/$', views.LibrariesList.as_view()),
    url(r'^paid_mass_enrollment$', views.PaidMassEnrollment.as_view()),
    url(r'^update_verified_cohort$', views.UpdateVerifiedCohort.as_view()),
]
