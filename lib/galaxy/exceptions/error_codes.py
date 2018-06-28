"""Defines the :class:`ErrorCode` class and instantiates concrete objects from JSON.

See the file error_codes.json for actual error code descriptions.
"""
from json import loads

from pkg_resources import resource_string


# Error codes are provided as a convience to Galaxy API clients, but at this
# time they do represent part of the more stable interface. They can change
# without warning between releases.
UNKNOWN_ERROR_MESSAGE = "Unknown error occurred while processing request."


class ErrorCode(object):
    """Small class allowing object representation for error descriptions loaded from JSON."""

    def __init__(self, code, default_error_message):
        """Construct a :class:`ErrorCode` from supplied integer and error message."""
        self.code = code
        self.default_error_message = default_error_message or UNKNOWN_ERROR_MESSAGE

    def __str__(self):
        """Return the error code message."""
        return str(self.default_error_message)

    def __repr__(self):
        """Return object representation of this error code."""
        return "ErrorCode[code=%d,message=%s]" % (self.code, str(self.default_error_message))

    def __int__(self):
        """Return the error code integer."""
        return int(self.code)


def _from_dict(entry):
    """Build a :class:`ErrorCode` object from a JSON entry."""
    name = entry.get("name")
    code = entry.get("code")
    message = entry.get("message")
    return (name, ErrorCode(code, message))


error_codes_json = resource_string(__name__, 'error_codes.json').decode("UTF-8")
for entry in loads(error_codes_json):
    name, error_code_obj = _from_dict(entry)
    globals()[name] = error_code_obj
