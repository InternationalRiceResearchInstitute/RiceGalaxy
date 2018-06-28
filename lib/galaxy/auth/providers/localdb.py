"""
Created on 16/07/2014

@author: Andrew Robinson
"""
import logging

from ..providers import AuthProvider

log = logging.getLogger(__name__)


class LocalDB(AuthProvider):
    """Authenticate users against the local Galaxy database (as per usual)."""
    plugin_type = 'localdb'

    def authenticate(self, email, username, password, options):
        """
        See abstract method documentation.
        """
        return (False, '', '')  # it can never auto-create based of localdb (chicken-egg)

    def authenticate_user(self, user, password, options):
        """
        See abstract method documentation.
        """
        user_ok = user.check_password(password)
        log.debug("User: %s, LOCALDB: %s" % (user.email, user_ok))
        return user_ok


__all__ = ('LocalDB', )
