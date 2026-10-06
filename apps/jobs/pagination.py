from rest_framework.pagination import CursorPagination

class JobCursorPagination(CursorPagination):
    page_size = 2
    ordering = '-created_at'
    cursor_query_param = 'cursor'