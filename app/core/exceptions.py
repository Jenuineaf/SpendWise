class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(404, detail)


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(409, detail)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(401, detail)


class ForbiddenError(AppException):
    def __init__(self, detail: str = "Not allowed to access this resource"):
        super().__init__(403, detail)


class BadRequestError(AppException):
    def __init__(self, detail: str = "Invalid request"):
        super().__init__(400, detail)
