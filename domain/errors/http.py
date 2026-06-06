from fastapi import HTTPException, status


class GenericError(HTTPException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Unexpected error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.default_detail,
        )


class InternalError(GenericError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Internal server error"


class ResourceNotFoundError(GenericError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"


class ResourceAlreadyExists(GenericError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource already exists"


class ResourceInUse(GenericError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource is in use"


class ForbiddenRequestError(GenericError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Forbidden request"


class KeyNotFoundError(GenericError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Required key not found"
