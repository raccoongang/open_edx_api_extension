import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils.decorators import method_decorator

from rest_framework.generics import RetrieveAPIView, ListAPIView
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from cors_csrf.decorators import ensure_csrf_cookie_cross_domain
from course_modes.models import CourseMode
from course_structure_api.v0 import serializers
from course_structure_api.v0.views import CourseViewMixin
from courseware import courses

from embargo import api as embargo_api
from instructor.offline_gradecalc import student_grades

from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError
from student.models import User, CourseEnrollment
from xmodule.modulestore.django import modulestore

from openedx.core.djangoapps.user_api.preferences.api import update_email_opt_in
from openedx.core.lib.api.authentication import (
    SessionAuthenticationAllowInactiveUser,
    OAuth2AuthenticationAllowInactiveUser,
)
from openedx.core.lib.api.serializers import PaginationSerializer
from openedx.core.lib.api.permissions import ApiKeyHeaderPermission, ApiKeyHeaderPermissionIsAuthenticated

from enrollment import api
from enrollment.errors import (
    CourseNotFoundError, CourseEnrollmentError,
    CourseModeNotFoundError, CourseEnrollmentExistsError
)
from enrollment.views import ApiKeyPermissionMixIn, EnrollmentCrossDomainSessionAuth, EnrollmentListView

from .data import get_course_enrollments

from open_edx_api_extension.serializers import CourseWithExamsSerializer
from .data import get_course_enrollments, get_user_proctored_exams

log = logging.getLogger(__name__)


class LibrariesList(ListAPIView):
    """
    **Use Case**
        Get a paginated list of libraries in the whole edX Platform.
        The list can be filtered by course_id.
        Each page in the list can contain up to 10 courses.
    **Example Requests**
          GET /api/extended/libraries/
    **Response Values**
        * count: The number of courses in the edX platform.
        * next: The URI to the next page of courses.
        * previous: The URI to the previous page of courses.
        * num_pages: The number of pages listing courses.
        * results:  A list of courses returned. Each collection in the list
          contains these fields.
            * id: The unique identifier for the course.
              "course".
            * org: The organization specified for the course.
            * course: The course number.
    """
    # Using EDX_API_KEY for access to this api
    authentication_classes = (SessionAuthenticationAllowInactiveUser,
                              OAuth2AuthenticationAllowInactiveUser)
    permission_classes = ApiKeyHeaderPermissionIsAuthenticated,

    def list(self, request, *args, **kwargs):
        lib_info = [
            {
                "display_name": lib.display_name,
                "library_key": unicode(lib.location.library_key),
                "org": unicode(lib.location.library_key.org),
            }
            for lib in modulestore().get_libraries()
            ]
        return Response(lib_info)


class CourseUserResult(CourseViewMixin, RetrieveAPIView):
    """
    **Use Case**

        Get result user for a specific course.

    **Example Request**:

        GET /api/extended/courses/{course_id}/{username}/

    **Response Values**

        * id: The unique identifier for the user.

        * username: The username of the user.

        * email: The email of the user.

        * realname: The realname of the user.

        * grade_summary: Contains student grade details:

            * section_breakdown: This is a list of dictionaries which provide details on sections that were graded:
                * category: A string identifying the category.
                * percent: A float percentage for the section.
                * detail: A string explanation of the score. E.g. "Homework 1 - Ohms Law - 83% (5/6)".
                * label: A short string identifying the section. E.g. "HW  3".

            * grade:  A final letter grade.

            * totaled_scores: totaled scores, which is passed to the grader.

            * percent: Contains a float value, which is the final percentage score for the student.

            * grade_breakdown: This is a list of dictionaries which provide details on the contributions
                               of the final percentage grade. This is a higher level breakdown, for when the grade is
                               constructed of a few very large sections (such as Homeworks, Labs, a Midterm, and a Final):
                * category: A string identifying the category.
                * percent: A float percentage in the breakdown. All percents should add up to the final percentage.
                * detail: A string explanation of this breakdown. E.g. "Homework - 10% of a possible 15%".
    """

    @CourseViewMixin.course_check
    def get(self, request, **kwargs):
        username = self.kwargs.get('username')
        enrolled_students = CourseEnrollment.objects.users_enrolled_in(
            self.course_key).filter(username=username)
        course = courses.get_course(self.course_key)

        if not enrolled_students:
            return Response({
                "error_description": "User is not enrolled for the course",
                "error": "invalid_request"
            })

        student_info = [
            {
                'username': student.username,
                'id': student.id,
                'email': student.email,
                'grade_summary': student_grades(student, request, course),
                'realname': student.profile.name,
            }
            for student in enrolled_students
            ]
        return Response(student_info)


class CourseListMixin(object):
    lookup_field = 'course_id'
    paginate_by = 10000
    paginate_by_param = 'page_size'
    pagination_serializer_class = PaginationSerializer
    serializer_class = serializers.CourseSerializer
    # Using EDX_API_KEY for access to this api
    authentication_classes = (SessionAuthenticationAllowInactiveUser,
                              OAuth2AuthenticationAllowInactiveUser)
    permission_classes = ApiKeyHeaderPermissionIsAuthenticated,

    def get_queryset(self):
        course_ids = self.request.QUERY_PARAMS.get('course_id', None)

        results = []
        if course_ids:
            course_ids = course_ids.split(',')
            for course_id in course_ids:
                course_key = CourseKey.from_string(course_id)
                course_descriptor = courses.get_course(course_key)
                results.append(course_descriptor)
        else:
            results = modulestore().get_courses()

        # Ensure only course descriptors are returned.
        results = (course for course in results if
                   course.scope_ids.block_type == 'course')

        # Sort the results in a predictable manner.
        return sorted(results, key=lambda course: unicode(course.id))


class CourseList(CourseListMixin, ListAPIView):
    """
    Inspired from:
    lms.djangoapps.course_structure_api.v0.views.CourseList

    **Use Case**
        Get a paginated list of courses in the whole edX Platform.
        The list can be filtered by course_id.
        Each page in the list can contain up to 10 courses.
    **Example Requests**
          GET /api/extended/courses/
    **Response Values**
        * count: The number of courses in the edX platform.
        * next: The URI to the next page of courses.
        * previous: The URI to the previous page of courses.
        * num_pages: The number of pages listing courses.
        * results:  A list of courses returned. Each collection in the list
          contains these fields.
            * id: The unique identifier for the course.
            * name: The name of the course.
            * category: The type of content. In this case, the value is always
              "course".
            * org: The organization specified for the course.
            * run: The run of the course.
            * course: The course number.
            * uri: The URI to use to get details of the course.
            * image_url: The URI for the course's main image.
            * start: The course start date.
            * end: The course end date. If course end date is not specified, the
              value is null.
    """
    serializer_class = serializers.CourseSerializer


class CourseListWithExams(CourseListMixin, ListAPIView):
    """
    Gets a list of courses with proctored exams
    """
    serializer_class = CourseWithExamsSerializer


class SSOEnrollmentListView(EnrollmentListView):
    """
    Inspired from:
    common.djangoapps.enrollment.views.EnrollmentListView
    See base docs in parent class or on the web
    http://edx-platform-api.readthedocs.org/en/latest/enrollment/enrollment.html#enrollment.views.EnrollmentView
    """

    @method_decorator(ensure_csrf_cookie_cross_domain)
    def get(self, request):
        """
        There is copy-paste from parent class method.
        Only one difference we use get_course_enrollments() instead api.get_enrollments

        Gets a list of all course enrollments for the currently logged in user.
        """
        username = request.GET.get('user',
                                   request.user.is_staff and None or request.user.username)
        try:
            course_key = CourseKey.from_string(request.GET.get('course_run'))
        except InvalidKeyError:
            course_key = None

        if (
            not request.user.is_staff and request.user.username != username) and not self.has_api_key_permissions(
                request):
            # Return a 404 instead of a 403 (Unauthorized). If one user is looking up
            # other users, do not let them deduce the existence of an enrollment.
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            if course_key:
                return Response(
                    get_course_enrollments(username, course_id=course_key))
            return Response(get_course_enrollments(username))
        except CourseEnrollmentError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": (
                        u"An error occurred while retrieving enrollments for user '{username}'"
                    ).format(username=username)
                }
            )


class PaidMassEnrollment(APIView, ApiKeyPermissionMixIn):
    """
        **Use Cases**

            1. Enroll the list of users to verified course mode

        **Example Requests**:

            POST /api/extended/enrollment{
                "course_details":{"course_id": "edX/DemoX/Demo_Course"},
                "users": "[user1, user2, user3]"
            }

        **Post Parameters**

            * users:  The usernames of the users. Required.

            * mode: The Course Mode for the enrollment. Individual users cannot upgrade their enrollment mode from
              'honor'. Only server-to-server requests can enroll with other modes. Optional.

            * is_active: A Boolean indicating whether the enrollment is active. Only server-to-server requests are
              allowed to deactivate an enrollment. Optional.

            * course details: A collection that contains:

                * course_id: The unique identifier for the course.

            * email_opt_in: A Boolean indicating whether the user
              wishes to opt into email from the organization running this course. Optional.

            * enrollment_attributes: A list of dictionary that contains:

                * namespace: Namespace of the attribute
                * name: Name of the attribute
                * value: Value of the attribute

        **Response Values**

            200 - OK, 400 - Fail
    """
    authentication_classes = OAuth2AuthenticationAllowInactiveUser, EnrollmentCrossDomainSessionAuth
    permission_classes = ApiKeyHeaderPermissionIsAuthenticated,

    @transaction.commit_on_success
    def post(self, request):
        """
        Enrolls the list of users in a verified course mode.
        """
        # Get the users, Course ID, and Mode from the request.

        users = request.DATA.get('users', [])

        if len(users) == 0:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"message": u"Users must be specified to create a new enrollment."}
            )

        course_id = request.DATA.get('course_details', {}).get('course_id')

        if not course_id:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"message": u"Course ID must be specified to create a new enrollment."}
            )

        try:
            course_id = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": u"No course '{course_id}' found for enrollment".format(course_id=course_id)
                }
            )

        # use verified course mode by default
        mode = request.DATA.get('mode', CourseMode.VERIFIED)

        bad_users = []
        list_users = []
        for username in users:
            try:
                user = User.objects.get(username=username)
                list_users.append(user)
            except ObjectDoesNotExist:
                bad_users.append(username)

        if len(bad_users) > 0:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'message': u'Users: {} does not exist.'.format(', '.join(bad_users))}
            )

        for user in list_users:
            embargo_response = embargo_api.get_embargo_response(request, course_id, user)

            if embargo_response:
                return embargo_response

        current_username = None
        try:
            is_active = request.DATA.get('is_active')
            # Check if the requested activation status is None or a Boolean
            if is_active is not None and not isinstance(is_active, bool):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={
                        'message': (u"'{value}' is an invalid enrollment activation status.").format(value=is_active)
                    }
                )

            enrollment_attributes = request.DATA.get('enrollment_attributes')
            errors = False
            already_paid = []  # list of users with verified enrollment
            not_enrolled = []  # list of not enrolled yet or unenrolled users
            for username in users:
                current_username = username
                enrollment = api.get_enrollment(username, unicode(course_id))
                if not enrollment:
                    not_enrolled.append(username)
                elif enrollment['is_active'] is not True:
                    not_enrolled.append(username)
                elif enrollment['mode'] == CourseMode.VERIFIED:
                    already_paid.append(username)
            msg_paid = u""
            msg_not_enrolled = u""
            if len(already_paid) > 0:
                msg_paid = u'Users: {} already paid for course.'.format(', '.join(already_paid))
                errors = True
            if len(not_enrolled) > 0:
                msg_not_enrolled = u'Users: {} not enrolled for course.'.format(', '.join(not_enrolled))
                errors = True
            if errors:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"message": (u"'{course_id}'\n:{msg_paid}\n{msg_not_enrolled}").format(
                        course_id=course_id,
                        msg_paid=msg_paid,
                        msg_not_enrolled=msg_not_enrolled
                    ),
                    })

            for username in users:
                current_username = username
                response = api.update_enrollment(username, unicode(course_id), mode=mode, is_active=is_active)

            email_opt_in = request.DATA.get('email_opt_in', None)
            if email_opt_in is not None:
                org = course_id.org
                for username in users:
                    update_email_opt_in(username, org, email_opt_in)

            return Response(
                status=status.HTTP_200_OK,
                data={
                    "message": u"Success for course '{course_id}'.".format(course_id=course_id)
                })
        except CourseModeNotFoundError as error:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": (
                        u"The course mode '{mode}' is not available for course '{course_id}'."
                    ).format(mode="verified", course_id=course_id),
                    "course_details": error.data
                })
        except CourseNotFoundError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": u"No course '{course_id}' found for enrollment".format(course_id=course_id)
                }
            )
        except CourseEnrollmentExistsError as error:
            return Response(data=error.enrollment)
        except CourseEnrollmentError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": (
                        u"An error occurred while creating the new course enrollment for user "
                        u"'{username}' in course '{course_id}'"
                    ).format(username=current_username, course_id=course_id)
                }
            )


class ProctoredExamsListView(APIView):
    """
    Get list of user's course and proctored exams for it
    """
    authentication_classes = (SessionAuthenticationAllowInactiveUser,
                              OAuth2AuthenticationAllowInactiveUser)

    def get(self, request, username):
        result = get_user_proctored_exams(username, request)

        return Response(data=result)
