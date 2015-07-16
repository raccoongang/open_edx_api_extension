from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from instructor.offline_gradecalc import student_grades
from course_structure_api.v0.views import CourseViewMixin
from courseware import courses
from student.models import CourseEnrollment


class CourseUserResult(CourseViewMixin, RetrieveAPIView):

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