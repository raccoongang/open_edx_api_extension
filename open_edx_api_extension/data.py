from django.core.urlresolvers import reverse
from edx_proctoring.api import get_all_exams_for_course
from student.models import CourseEnrollment
from enrollment.serializers import CourseEnrollmentSerializer
from datetime import datetime, timedelta


def get_course_enrollments(user_id=None, **kwargs):
    """
    Retrieve a list representing all aggregated data for a user's course enrollments.
    Construct a representation of all course enrollment data for a specific user.
    Args:
        user_id (str): The name of the user to retrieve course enrollment information for.
    Returns:
        A serializable list of dictionaries of all aggregated enrollment data for a user.
    """
    qset = CourseEnrollment.objects.filter(is_active=True, **kwargs)
    if user_id is not None:
        qset = qset.filter(user__username=user_id)
    qset = qset.order_by('created')
    return CourseEnrollmentSerializer(qset).data  # pylint: disable=no-member


def get_user_proctored_exams(username, request):
    enrolments = CourseEnrollment.objects.filter(is_active=True,
                                                 user__username=username)
    result = {}
    for enrolment in enrolments:
        course = enrolment.course
        course_id = str(course.id)
        if course_id not in result:
            end = course.end
            if not end:
                limit = course.time_limit_mins or 0
                end = (datetime.strptime(course.start, '%Y-%m-%dT%H:%M:%SZ') + timedelta(minutes=limit)).isoformat()
                end = '{}Z'.format(end)
            result[course_id] = {
                "id": course_id,
                "name": course.display_name,
                "uri": request.build_absolute_uri(
                    reverse('course_structure_api:v0:detail',
                            kwargs={'course_id': course_id})),
                "image_url": course.course_image_url,
                "start": course.start,
                "end": end,
                'exams': []
            }
            exams = get_all_exams_for_course(course_id=course.id)
            for exam in exams:
                if exam['is_proctored'] == True:
                    result[course_id]['exams'].append(exam)
            result = {key: value for key, value in result.items() if
                      len(value['exams']) > 0}
    return result
