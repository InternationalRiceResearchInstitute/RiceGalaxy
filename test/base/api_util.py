import os

DEFAULT_GALAXY_MASTER_API_KEY = "TEST123"
DEFAULT_GALAXY_USER_API_KEY = None


def get_master_api_key():
    """ Test master API key to use for functional test. This key should be
    configured as a master API key and should be able to create additional
    users and keys.
    """
    for key in ["GALAXY_CONFIG_MASTER_API_KEY", "GALAXY_CONFIG_OVERRIDE_MASTER_API_KEY"]:
        value = os.environ.get(key, None)
        if value:
            return value
    return DEFAULT_GALAXY_MASTER_API_KEY


def get_user_api_key():
    """ Test user API key to use for functional tests. If set, this should drive
    API based testing - if not set master API key should be used to create a new
    user and API key for tests.
    """
    return os.environ.get("GALAXY_TEST_USER_API_KEY", DEFAULT_GALAXY_USER_API_KEY)
