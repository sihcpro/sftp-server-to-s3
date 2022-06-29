from sftpserver import settings
from sftpserver.s3_operation import S3Operation

s3 = S3Operation(settings.AWS_ACCESS_KEY, settings.AWS_SECRET_KEY)

buckets = s3.get_all_buckets()
bucket_name = buckets[0].name
print("bucket_name", bucket_name)
bucket = s3.connection.get_bucket(bucket_name)

# key_name = "test1/"
# key = bucket.get_key(key_name)
# print("key", key.__dict__)


# bucket.list("", "/")
