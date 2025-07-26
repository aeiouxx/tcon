from enum import Enum

# python <= 3.10 no HTTPMethod in stdlib


class HTTPMethod(str, Enum):
    DELETE = "DELETE"
    GET = "GET"
    POST = "POST"
