from rest_framework.views import exception_handler
from rest_framework.response import Response


def standardized_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        formatted_data = {
            "success" : False,
            "status_code" : response.status_code,
            "error_type" : exc.__class__.__name__,
            "details" : response.data
        }
        response.data = formatted_data
        return response