class AppError(Exception):
    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details=None, status: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.details = details or {}


class ValidationError(AppError):
    status = 422
    code = "VALIDATION"


class Unauthorized(AppError):
    status = 401
    code = "UNAUTHENTICATED"


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN"


class NotFound(AppError):
    """Also used for records outside the user's scope (no existence disclosure)."""
    status = 404
    code = "NOT_FOUND"

    def __init__(self, message="السجل غير موجود أو لا تملك صلاحية الوصول إليه", **kw):
        super().__init__(message, **kw)


class Conflict(AppError):
    status = 409
    code = "CONFLICT"


class RuleBlocked(AppError):
    """A clinical/safety/workflow rule prevents the action."""
    status = 409
    code = "RULE_BLOCKED"
