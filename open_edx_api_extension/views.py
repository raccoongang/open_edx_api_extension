from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from instructor.offline_gradecalc import student_grades
from course_structure_api.v0.views import CourseViewMixin
from courseware import courses
from student.models import CourseEnrollment


class CourseUserResult(CourseViewMixin, RetrieveAPIView):
    """
    **Use Case**

        Get result user for a specific course.

    **Example Request**:

        GET api/course_user_result/courses/{course_id}/{username}/

    **Response Values**

        * id: The unique identifier for the user.

        * username: The username of the user.

        * email: The email of the user.

        * realname: The realname of the user.

        * grade_summary: A collection that includes:

            * section_breakdown: A collection that includes:
                * category: Assignment type name.
                * percent: .
                * detail: .
                * label: Abbreviation.

            * grade: .

            * totaled_scores: .

            * percent: .

            * grade_breakdown: A collection that includes:
                * category: Assignment type name.
                * percent: .
                * detail:
    """

    @CourseViewMixin.course_check
    def get(self, request, **kwargs):
        username = self.kwargs.get('username')
        enrolled_students = CourseEnrollment.objects.users_enrolled_in(self.course_key).filter(username=username)
        course = courses.get_course(self.course_key)

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