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