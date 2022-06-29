# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distrubuted in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
A stub SFTP server for loopback SFTP testing.
"""

import io
import os
import tempfile
import time
from calendar import c
from datetime import datetime
from importlib.resources import path

import requests
from boto.exception import S3CreateError, S3ResponseError
from boto.s3.bucketlistresultset import BucketListResultSet
from helper.debug import function_debuger, function_debuger_with_resule
from helper.logger import logger
from paramiko import (
    ServerInterface,
    SFTPAttributes,
    SFTPHandle,
    SFTPServer,
    SFTPServerInterface,
)
from paramiko.common import (
    AUTH_FAILED,
    AUTH_PARTIALLY_SUCCESSFUL,
    AUTH_SUCCESSFUL,
    OPEN_SUCCEEDED,
)
from paramiko.sftp import SFTP_OK

from . import settings
from .s3_operation import S3Operation

FULL_CONTROL_MODE_FLAG = 0o600
DIR_MODE_FLAG = 0o40600

cloud_sep = "/"
ftp_sep = os.sep


def asciify(string):
    # Try to convert string to a legible format for non-Unicode clients.
    try:
        return string.encode("utf-8")
    except:
        return string


class StubServer(ServerInterface):
    AUTH_SERVER_URI = settings.AUTH_SERVER_URI
    AUTH_URL = settings.AUTH_URL

    @function_debuger
    def check_auth_none(self, username):
        return AUTH_FAILED

    @function_debuger(print_input=True)
    def check_auth_password(self, username, password):
        resp = requests.post(
            self.AUTH_URL, json={"username": username, "password": password}
        )
        if resp.status_code == 200:
            return AUTH_SUCCESSFUL
        else:
            return AUTH_FAILED

    @function_debuger(print_input=True)
    def check_auth_publickey(self, username, key):
        resp = requests.post(
            self.AUTH_URL, json={"username": username, "key": str(key)}
        )
        if resp.status_code == 200:
            return AUTH_SUCCESSFUL
        else:
            return AUTH_FAILED

    @function_debuger
    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED

    @function_debuger
    def get_allowed_auths(self, username):
        """List availble auth mechanisms."""
        return "none,password,publickey"


class StubSFTPHandle(SFTPHandle):
    @function_debuger
    def stat(self):
        try:
            return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    @function_debuger
    def chattr(self, attr):
        # python doesn't have equivalents to fchown or fchmod, so we have to
        # use the stored filename
        try:
            SFTPServer.set_file_attr(self.filename, attr)
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)


class S3Handler(SFTPHandle):
    @function_debuger
    def __init__(self, username, bucket, obj_name, mode, flags, s3: S3Operation):
        super(S3Handler, self).__init__(flags)
        self.username = username
        self.bucket = bucket
        self.name = obj_name
        self.mode = mode
        self.closed = False
        self.total_size = 0
        self.temp_file_path = None
        self.temp_file = None
        self.s3 = s3
        logger.info(
            "Creating S3Handler(%s,%s,%s,%s)" % (username, bucket, obj_name, mode)
        )

        if not all([bucket, obj_name]):
            self.closed = True
            raise IOError(1, "Operation not permitted")

        try:
            self.bucket = self.s3.connection.get_bucket(self.bucket)
        except:
            raise IOError(2, "No such file or directory")

        try:
            self.obj = self.bucket.get_key(self.name)
        except:
            logger.error("No such file or directory")

    @function_debuger
    def init_temp_file(self):
        self.obj = self.bucket.get_key(self.name)
        if not self.obj:
            # key does not exist, create it
            self.obj = self.bucket.new_key(self.name)
        # create a temporary file
        self.temp_file_path = tempfile.mkstemp()[1]
        self.temp_file = open(self.temp_file_path, "wb")

    @function_debuger
    def write(self, offset, data):
        if "w" not in self.mode:
            raise OSError(1, "Operation not permitted")
        if self.temp_file is None:
            self.init_temp_file()
        self.temp_file.write(data)
        return SFTP_OK

    @function_debuger
    def close(self):
        if "w" not in self.mode:
            return
        self.temp_file.close()
        try:
            self.obj.set_contents_from_filename(self.temp_file_path)
        except S3ResponseError as e:
            # Avoid crashing when the "directory" vanished while we were processing it.
            # This is actually due to a server error. It seems to happen after
            # a "rm file" command incorrectly deletes an entire directory. (!!!)
            logger.error(
                "Directory vanished! could not set contents from file %s "
                % (self.temp_file_path)
            )
            return

        self.obj.close()

        # clean up the temporary file
        os.remove(self.temp_file_path)
        self.temp_file_path = None
        self.temp_file = None

    @function_debuger(print_input=True)
    def read(self, offset, length):
        if "r" not in self.mode:
            raise OSError(1, "Operation not permitted")

        # file_stream = io.StringIO()
        # self.obj.download_fileobj(file_stream)
        return self.obj.read(length)

    @function_debuger
    def seek(self, *kargs, **kwargs):
        raise IOError(1, "Operation not permitted")

    @function_debuger
    def stat(self):
        try:
            return SFTPAttributes.from_stat(
                os.stat_result(
                    [FULL_CONTROL_MODE_FLAG, 0, 0, 0, 0, 0, self.obj.size, 0, 0, 0]
                )
            )
        except Exception as e:
            logger.exception(e)
            return SFTPServer.convert_errno(-1)

    @function_debuger
    def chattr(self, attr):
        # python doesn't have equivalents to fchown or fchmod, so we have to
        # use the stored filename
        try:
            SFTPServer.set_file_attr(self.name, attr)
            return SFTP_OK
        except Exception as e:
            logger.exception(e)
            return SFTPServer.convert_errno(-1)


class StubSFTPServer(SFTPServerInterface):
    # assume current folder is a fine root
    # (the tests always create and eventualy delete a subfolder, so there shouldn't be any mess)
    ROOT = os.getcwd()

    @function_debuger
    def connect_s3(self, key, secret):
        self.s3 = S3Operation(key, secret)

    @function_debuger(print_input=True, print_output=True)
    def parse_fspath(self, path):
        """Returns a (username, site, filename) tuple. For shorter paths
        replaces not-provided values with empty strings.
        """
        if path == ".":
            path = "/"
        logger.info("parse_fspath(%s)" % (path))
        if not path.startswith(ftp_sep):
            raise ValueError(
                "parse_fspath: You have to provide a full path, not %s" % path
            )
        parts = path.split(ftp_sep)
        if len(parts) > 3:
            # join extra 'directories' into key
            # Conveting os.sep (which was unfortunately introduced by pyftpdlib)
            # to cloud_sep
            parts = parts[0], parts[1], cloud_sep.join(parts[2:])
        while len(parts) < 3:
            parts.append("")
        return tuple(parts)

    @function_debuger
    def realpath(self, path):
        return path

    @function_debuger
    def get_basename(self, aws_path: str):
        if aws_path.endswith(cloud_sep):
            return os.path.basename(aws_path[:-1]) + cloud_sep
        return os.path.basename(aws_path)

    @function_debuger(print_input=True, print_output=True)
    def get_list_dir(self, path):
        """ "Return an iterator object that yields a directory listing
        in a form suitable for LIST command.
        """
        try:
            _, bucket, obj = self.parse_fspath(path)
        except (ValueError):
            raise OSError(2, "No such file or directory")

        if not bucket and not obj:
            buckets = self.s3.get_all_buckets()
            logger.info("------ 1 %r", buckets)
            return buckets

        if bucket and not obj:
            try:
                objects = self.s3.connection.get_bucket(bucket_name=bucket).list(
                    delimiter=cloud_sep
                )
            except:
                raise OSError(2, "No such file or directory")
            logger.info("------ 2 %r", objects)
            for obj in objects:
                logger.debug("------ %r", obj.__dict__)
            return objects
            return list(self.format_list_objects(objects))

        if bucket and obj:
            # This is a key, which is not supported literally as a directory.
            # Try interpreting as a hierarchical key:
            obj += cloud_sep  # Because S3 add a cloud_sep and the end of the file name
            try:
                objects = self.s3.connection.get_bucket(bucket_name=bucket).list(
                    prefix=obj, delimiter=cloud_sep
                )
            except:
                raise OSError(2, "No such file or directory")
            logger.info("------ 3 %r", objects)
            return [i for i in list(objects) if i.name != obj]
            return list(self.format_list_objects(objects))

    @function_debuger(print_input=True, print_output=True)
    def list_folder(self, path):
        logger.info("--------------- path %r", path)
        if path == "/":
            buckets = self.s3.get_all_buckets()
            logger.info("buckets %r", buckets[0].__dict__)
            return [
                SFTPAttributes.from_stat(
                    os.stat_result([DIR_MODE_FLAG, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                    filename=bucket.name,
                )
                for bucket in buckets
            ]
        else:
            buckets = self.get_list_dir(path)
        st_size = 0
        return [
            SFTPAttributes.from_stat(
                os.stat_result(
                    [FULL_CONTROL_MODE_FLAG, 0, 0, 0, 0, 0, st_size, 0, 0, 0]
                ),
                filename=self.get_basename(bucket.name),
            )
            for bucket in buckets
        ]

    @function_debuger
    def lexists(self, path):
        try:
            _, bucket_name, key_name = self.parse_fspath(path)
        except (ValueError):
            raise OSError(2, "No such file or directory")

        if not bucket_name and not key_name:
            return True  # root

        if bucket_name and not key_name:
            try:
                bucket = self.s3.connection.get_bucket(bucket_name)
                objects = bucket.list()
            except:
                raise OSError(2, "No such file or directory")
            return path in objects

        if bucket_name and key_name:
            bucket = self.s3.connection.get_bucket(bucket_name)
            return not (not bucket.get_key(key_name))

    @function_debuger
    def stat(self, path):
        self.connect_s3(settings.AWS_ACCESS_KEY, settings.AWS_SECRET_KEY)
        st_mode = FULL_CONTROL_MODE_FLAG
        _, bucket_name, key_name = self.parse_fspath(path)

        st_size = 0

        try:
            if not key_name:  # Bucket
                # Return a part-bogus stat with the data we do have.
                st_mode = st_mode | DIR_MODE_FLAG

            else:  # Key
                bucket = self.s3.connection.get_bucket(bucket_name)
                if key_name[-1] == cloud_sep:  # Virtual directory for hierarchical key.
                    st_mode = st_mode | DIR_MODE_FLAG
                else:
                    obj = bucket.get_key(key_name)
                    # Workaround os.sep crap.
                    if obj is None:
                        obj = bucket.get_key(key_name.replace(cloud_sep, os.sep))
                    if obj is None:
                        # Key is a folder will end with a cloud_sep
                        st_mode = st_mode | DIR_MODE_FLAG
                        obj = bucket.get_key(key_name + cloud_sep)
                    if obj is None:
                        logger.error(
                            "Cannot find object for path %s , key %s in bucket %s "
                            % (path, key_name, bucket_name)
                        )
                        raise OSError(2, "No such file or directory")
                    st_size = obj.size

            return SFTPAttributes.from_stat(
                os.stat_result(
                    [st_mode, 0, 0, 0, 0, 0, st_size, 0, 0, 0]
                )  # FIXME more stats (mtime)
            )
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        except Exception as e:
            logger.error(
                "Failed stat(%s) %s %s: %s " % (path, bucket_name, key_name, e)
            )
            raise OSError(2, "No such file or directory")

        path = self.realpath(path)
        try:
            return SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    lstat = stat
    exists = lexists

    @function_debuger
    def open(self, path, flags, attr):
        # mode = getattr(attr, "st_mode", "erw")
        mode = "wr"
        username, bucket, obj = self.parse_fspath(path)
        return S3Handler(username, bucket, obj, mode, 0o666, s3=self.s3)

    @function_debuger
    def remove(self, path):
        _, bucket, name = self.parse_fspath(path)

        if not name:
            raise OSError(13, "Operation not permitted")

        try:
            bucket = self.s3.connection.get_bucket(bucket)
            bucket.delete_key(name)
        except:
            raise OSError(2, "No such file or directory")
        return not name

    @function_debuger
    def isdir(self, path):
        return path.endswith(cloud_sep)

    @function_debuger
    def mkdir(self, path, attr):
        _, bucket_name, obj_name = self.parse_fspath(path)
        try:
            if obj_name:
                bucket = self.s3.connection.get_bucket(bucket_name)
                if not obj_name.endswith(cloud_sep):
                    obj_name += cloud_sep
                new_folder = bucket.new_key(obj_name)
                new_folder.set_contents_from_string("")
            else:
                self.s3.connection.create_bucket(bucket_name)
        except (ValueError):
            raise OSError(2, "No such file or directory")
        return SFTP_OK

    @function_debuger
    def rmdir(self, path):
        _, bucket_name, obj_name = self.parse_fspath(path)

        # If the user requests 'rmdir' of a file, refuse that.
        # This is important to avoid falling through to delete an entire bucket!
        try:
            if obj_name:
                bucket = self.s3.connection.get_bucket(bucket_name)
                if not obj_name.endswith(cloud_sep):
                    obj_name += cloud_sep
                objects = self.s3.connection.get_bucket(bucket_name=bucket).list(
                    prefix=obj_name, delimiter=cloud_sep
                )
                obj = None
                for o in objects:
                    if o.name == obj_name:
                        obj = o
                        break

                if obj is None:
                    raise OSError(2, "No such file or directory")
                else:
                    obj.delete()
            else:
                try:
                    bucket = self.s3.connection.get_bucket(bucket)
                except:
                    raise OSError(2, "No such file or directory")

                try:
                    self.s3.connection.delete_bucket(bucket)
                except:
                    raise OSError(39, "Directory not empty: '%s'" % bucket)
        except Exception:
            raise OSError(39, "Directory not empty: '%s'" % bucket)

        return SFTP_OK

    # @function_debuger
    # def open(self, path, flags, attr):
    #     path = self._realpath(path)
    #     try:
    #         binary_flag = getattr(os, "O_BINARY", 0)
    #         flags |= binary_flag
    #         mode = getattr(attr, "st_mode", None)
    #         if mode is not None:
    #             fd = os.open(path, flags, mode)
    #         else:
    #             # os.open() defaults to 0777 which is
    #             # an odd default mode for files
    #             fd = os.open(path, flags, 0o666)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     if (flags & os.O_CREAT) and (attr is not None):
    #         attr._flags &= ~attr.FLAG_PERMISSIONS
    #         SFTPServer.set_file_attr(path, attr)
    #     if flags & os.O_WRONLY:
    #         if flags & os.O_APPEND:
    #             fstr = "ab"
    #         else:
    #             fstr = "wb"
    #     elif flags & os.O_RDWR:
    #         if flags & os.O_APPEND:
    #             fstr = "a+b"
    #         else:
    #             fstr = "r+b"
    #     else:
    #         # O_RDONLY (== 0)
    #         fstr = "rb"
    #     try:
    #         f = os.fdopen(fd, fstr)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     fobj = StubSFTPHandle(flags)
    #     fobj.filename = path
    #     fobj.readfile = f
    #     fobj.writefile = f
    #     return fobj

    # @function_debuger
    # def remove(self, path):
    #     path = self._realpath(path)
    #     try:
    #         os.remove(path)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     return SFTP_OK

    # @function_debuger
    # def rename(self, oldpath, newpath):
    #     oldpath = self._realpath(oldpath)
    #     newpath = self._realpath(newpath)
    #     try:
    #         os.rename(oldpath, newpath)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     return SFTP_OK

    # @function_debuger
    # def mkdir(self, path, attr):
    #     path = self._realpath(path)
    #     try:
    #         os.mkdir(path)
    #         if attr is not None:
    #             SFTPServer.set_file_attr(path, attr)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     return SFTP_OK

    # @function_debuger
    # def rmdir(self, path):
    #     path = self._realpath(path)
    #     try:
    #         os.rmdir(path)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     return SFTP_OK

    # @function_debuger
    # def chattr(self, path, attr):
    #     path = self._realpath(path)
    #     try:
    #         SFTPServer.set_file_attr(path, attr)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    # return SFTP_OK

    # @function_debuger
    # def symlink(self, target_path, path):
    #     path = self._realpath(path)
    #     if (len(target_path) > 0) and (target_path[0] == "/"):
    #         # absolute symlink
    #         target_path = os.path.join(self.ROOT, target_path[1:])
    #         if target_path[:2] == "//":
    #             # bug in os.path.join
    #             target_path = target_path[1:]
    #     else:
    #         # compute relative to path
    #         abspath = os.path.join(os.path.dirname(path), target_path)
    #         if abspath[: len(self.ROOT)] != self.ROOT:
    #             # this symlink isn't going to work anyway -- just break it immediately
    #             target_path = "<error>"
    #     try:
    #         os.symlink(target_path, path)
    #     except OSError as e:
    #         return SFTPServer.convert_errno(e.errno)
    #     return SFTP_OK

    @function_debuger
    def readlink(self, path):
        return self.realpath(path)

    @function_debuger(print_input=True, print_output=True)
    def readdir(self, path):
        return self.realpath(path)
