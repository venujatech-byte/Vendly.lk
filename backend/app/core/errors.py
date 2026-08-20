class ApiError(Exception):
    """An expected API error that can be safely returned to the client."""

    def __init__(self, code, message, status_code=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def api_error_payload(error):
    payload = {
        "error": {
            "code": error.code,
            "message": error.message,
        },
    }

    if error.details is not None:
        payload["error"]["details"] = error.details

    return payload
