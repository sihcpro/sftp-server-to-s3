import os

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

AUTH_SERVER_URI = os.getenv("AUTH_SERVER_URI", "http://localhost:8000")
AUTH_URL = os.getenv(
    "AUTH_URL", f"{AUTH_SERVER_URI}/healthscreen/sftp-account/authentication/"
)
