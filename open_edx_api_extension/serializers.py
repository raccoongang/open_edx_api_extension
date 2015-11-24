from collections import OrderedDict
from rest_framework import serializers
try:
    from rest_framework.fields import SkipField
except ImportError:
    SkipField = Exception
from edx_proctoring.api import get_all_exams_for_course

from course_structure_api.v0.serializers import CourseSerializer



class CourseWithExamsSerializer(CourseSerializer):
    proctored_exams = serializers.SerializerMethodField("get_proctored_exams")
    regular_exams = serializers.SerializerMethodField("get_regular_exams")

    def __init__(self, *args, **kwargs):
        self.include_expired = kwargs.pop("include_expired", False)
        super(CourseWithExamsSerializer, self).__init__(*args, **kwargs)

    def get_proctored_exams(self):
        return self._get_exams(True)

    def get_regular_exams(self):
        return self._get_exams(False)

    def _get_exams(self, is_proctored):
        exams = get_all_exams_for_course(course_id=self.course_id)
        result = []
        for exam in exams:
            if exam.get('is_proctored') == self.is_proctored:
                result.append(exam)
        return result

