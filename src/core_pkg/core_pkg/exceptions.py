class CoreException(Exception):
    pass

class ServiceCallException(CoreException):
    """Service call failed"""

class NodeException(CoreException):
    """Node failed"""

class NodeExceptionRecoverable(NodeException):
    """Node failed with a recoverable error"""
class NodeExceptionNonRecoverable(NodeException):
    """Node failed with a non-recoverable error"""

class RWSException(CoreException):
    """RWS (Robot Web Services) communication exception"""


# Database exceptions

class DbServiceException(CoreException):
    """Base exception for service layer"""
    pass

class ValidationError(DbServiceException):
    """Raised when validation fails"""
    pass

class PermissionError(DbServiceException):
    """Raised when user doesn't have permission"""
    pass

class NotFoundError(DbServiceException):
    """Raised when entity is not found"""
    pass

class AuthenticationError(DbServiceException):
    """Raised when authentication fails"""
    pass
