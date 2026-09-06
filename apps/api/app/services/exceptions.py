class ServiceError(Exception):
    """Base class for errors raised by the service layer."""


class EmailAlreadyExistsError(ServiceError):
    pass


class InvalidCredentialsError(ServiceError):
    pass


class InvalidRefreshTokenError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass
