class AuthorizationError(Exception):
    """Base class for authorization exceptions"""
    pass

class SessionAccessError(AuthorizationError):
    """Raised when user tries to access unauthorized session"""
    pass