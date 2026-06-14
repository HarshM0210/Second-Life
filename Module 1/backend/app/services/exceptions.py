"""
Custom exception classes for pipeline services.
"""


class ServiceError(Exception):
    """Raised when a service encounters an unrecoverable error.

    Includes a user-facing message prompting retry.
    """

    def __init__(self, message: str, service: str | None = None):
        self.message = message
        self.service = service
        super().__init__(message)
