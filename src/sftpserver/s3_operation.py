from boto.exception import S3CreateError, S3ResponseError
from boto.s3.connection import S3Connection
from helper.debug import function_debuger
from helper.logger import logger


class S3Operation(object):
    """Storing connection object."""

    @function_debuger
    def __init__(self, key, secret, username=None):
        self.username = username or key
        self.key = key
        self._secret = secret
        self.connection = S3Connection(
            aws_access_key_id=key, aws_secret_access_key=secret
        )

    @function_debuger
    def get_all_buckets(self):
        try:
            return list(self.connection.get_all_buckets())
        except S3ResponseError as e:
            logger.exception(e)
            raise OSError(1, "S3 error (probably bad credentials)" + str(e))

    @function_debuger
    def __repr__(self):
        return self.connection
