"""Pagination for standard list endpoints (spec §6: ``?page=``, ``?page_size=``)."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
