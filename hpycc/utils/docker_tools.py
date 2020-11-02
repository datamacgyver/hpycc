"""
Functions to create and control HPCC docker images. Requires Docker to
be installed and running!!!!!!!
"""

from io import BytesIO
import tarfile
from pathlib import Path

import pkg_resources
import time

import docker
from docker.errors import NotFound
from passlib.apache import HtpasswdFile


class HPCCContainer:
    def __init__(self, tag="latest", name="hpycc_test_img", users=None,
                 pull=True, start=True):
        self.tag = tag
        self.client = docker.from_env()
        self.name = name
        self.image = "datamacgyver/hpcc-6-4-40-1"
        if users:
            self.users = users
        else:
            self.users = []

        if pull:
            self.pull_image()

        if start:
            try:
                self.container = self.start_container()
                self.setup_hpcc()
                self.start_hpcc()
            except Exception as e:
                self.stop_container()
                raise e

    def pull_image(self):
        for line in self.client.api.pull(self.image, tag=self.tag, stream=True):
            print(line.decode())

    def stop_container(self):
        try:
            self.client.containers.get(self.name).stop()
        except NotFound:
            pass
        else:
            self.client.api.remove_container(self.name)

    def start_container(self):
        try:
            container = self.client.containers.run(
                "{}:{}".format(self.image, self.tag), "/bin/bash",
                detach=True, auto_remove=False, tty=True,
                ports={"8010/tcp": 8010, "8015/tcp": 8015}, name=self.name)
        except (ValueError, FileNotFoundError) as e:
            self.stop_container()
            raise e
        else:
            return container

    def create_passwords(self):
        ht = HtpasswdFile()

        if not len(self.users):
            return b""

        elif isinstance(self.users[0], tuple):
            # now we have multiple users
            for user, password in self.users:
                ht.set_password(user, password)
        else:
            ht.set_password(self.users[0], self.users[1])

        return ht.to_string()

    def put_archive(self, b, name, path):
        pw_tarstream = BytesIO()

        tarinfo = tarfile.TarInfo(name=name)
        tarinfo.size = len(b)
        tarinfo.mtime = time.time()

        with tarfile.TarFile(fileobj=pw_tarstream, mode="w") as pw_tar:
            pw_tar.addfile(tarinfo, BytesIO(b))
        pw_tarstream.seek(0)
        self.container.put_archive(data=pw_tarstream, path=path)

    def setup_hpcc(self):
        if self.users:
            passwd_file = self.create_passwords()
            env_path = Path(
                pkg_resources.resource_filename(__name__, "environment.xml"))
            env_data = Path(env_path).read_bytes()
            self.put_archive(env_data, "environment.xml", "etc/HPCCSystems")
            self.put_archive(passwd_file, ".htpasswd", "etc/HPCCSystems")

    def start_hpcc(self):
        self.container.exec_run("etc/init.d/hpcc-init start")
        time.sleep(20)


if __name__ == '__main__':
    HPCCContainer(tag="7.12.4-1")
