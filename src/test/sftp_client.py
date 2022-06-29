from base64 import decodebytes

from paramiko import AutoAddPolicy, PublicBlob, RSAKey, SSHClient

keydata = b"""AAAAB3NzaC1yc2EAAAADAQABAAACAQDdeY8+nMsh3tZtodBivCvO+iqczMM9boP1W/cNXysp67s684RLTfypAAo7a/tVYOhknWa+ae+HW+vZYweo/G7yGye5RJFP03nmorwZvGHNizwFvbmXc04lny4oH+aDKUSPl+XCUCyR8J5eB5bmF4ExLz+YTIDPPR+cUiZlNlAPPNgsUjHiZiK++U1ky5eOZjxuF8kUO8EXAQ5rnX43xw03RrOYUMjByqDXZI2NljFX6tiNS/B13IzFMvfx5OQ2BPs039C50K9p76EUoDUdOVTlUPvX68ttswRYpNsVyIJJsh+ouMZKh/VGyfUW6RMCuV9FMCwj94rPG4Jj8mHPo+spQ6CRMwOjSnB9pJo9xqVy5RKgs8P2X/buK9iUOMqUvfQQUXVZyP931xF9aHOj3Ub75QMbFOMs+NYSSTABTmXUniWzrvg4QFQqbxJMxMFFa1a/mbxuHKrPTjyfM4OdvD73Pq7RNBiAtJD77VgqnCKymHBiJko/N4jWvHipCNJb94Fe9M2lILG/SdbLComGf6vEz6dVlwJZBso6B5im7U11kSUnpIjhQ6FzKWRgcFU2uGD1b5y1n1fy9mHpQw+wIYKvQctYHZzNY8cnGr01O0dgyovnYtCVyqwiu1ahvQNTnsj+I+pU8V4BAs0BuC3iG4W3ptGtFyolPW5Qcf5IRehmLw=="""
key = RSAKey(filename="/home/sihc/Test/demo")
# key = RSAKey(filename="/home/sihc/.ssh/id_rsa_test.pub", password="s")

client = SSHClient()
client.load_system_host_keys()
# client.get_host_keys().add("localhost", "ssh-rsa", key)
client.set_missing_host_key_policy(AutoAddPolicy())
client.connect("localhost", port=3377, username="sihc", password="123")
client.connect("localhost", port=3377, username="chi123", password="123456")
client.connect(
    "localhost",
    port=3377,
    # username="sihc",
    # password="123",
    # pkey=key,
    key_filename="/home/sihc/.ssh/id_rsa.pub",
)

client.connect(
    "localhost", port=3377, username="chi123", key_filename="/home/sihc/Test/demo.pub"
)

# stdin, stdout, stderr = client.exec_command("ls -l")

a = client.open_sftp()
a.stat(".")
a.listdir()
