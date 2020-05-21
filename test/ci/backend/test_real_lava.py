import os
import unittest
from django.test import TestCase
from squad.ci.models import Backend, TestJob
from squad.core.models import Group, Project


QEMU_JOB_DEFINITION = """
timeouts:
  job:
    minutes: 50
  connection:
    minutes: 2
context:
  arch: i386
  guestfs_interface: virtio
device_type: qemu
job_name: bar
priority: 78
visibility: public
actions:
- deploy:
    namespace: target
    timeout:
      minutes: 15
    to: tmpfs
    images:
      kernel:
        image_arg: -kernel {kernel} --append "root=/dev/sda  rootwait console=ttyS0,115200"
        url: http://snapshots.linaro.org/openembedded/lkft/lkft/sumo/intel-core2-32/lkft/linux-stable-rc-5.6/31/bzImage--5.6+git0+63c3d49741-r0-intel-core2-32-20200430003459-31.bin
      rootfs:
        image_arg: -hda {rootfs} -m 4096 -smp 4 -nographic
        url: http://snapshots.linaro.org/openembedded/lkft/lkft/sumo/intel-core2-32/lkft/linux-stable-rc-5.6/31/rpb-console-image-lkft-intel-core2-32-20200430003459-31.rootfs.ext4.gz
        compression: gz
    os: oe
- boot:
    namespace: target
    timeout:
      minutes: 10
    method: qemu
    media: tmpfs
    auto_login:
      login_prompt: 'login:'
      username: root
      login_commands:
      - su
    prompts:
    - 'root@intel-core2-32:'
- test:
    namespace: target
    timeout:
      minutes: 30
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: prep-tmp-disk
          description: Link /scratch to /tmp
        run:
          steps:
          - df -h
          - ln -s /tmp /scratch
      name: prep-tmp-disk
      path: inline/prep.yaml
"""


lava_test = unittest.skipUnless(
    os.environ.get('START_LAVA', False) == 'yes', 'Requires running LAVA instance'
)


class RealLavaRPC2Test(TestCase):

    def setUp(self):
        self.backend = Backend.objects.create(
            url='http://localhost/RPC2/',
            username='squadtest',
            token='kz8wyxmldwahe4w4086ceadedfwd0z7tadr87i60u1z30xymq38xy35ji98f0h6fgqmpwr3161zq87dytza70iqyhx5ab6xrzgh5lp1ghbcbrb0q650x8tpkgrm0a9n7',
            implementation_type='lava',
            backend_settings='',
        )
        self.group = Group.objects.create(
            name="group_foo"
        )
        self.project = Project.objects.create(
            name="project_foo",
            group=self.group,
        )
        self.build = self.project.builds.create(version='1')

    @lava_test
    def test_submit(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()
        self.assertEqual('bar', testjob.name)
        self.assertIsNotNone(testjob.job_id)

    @lava_test
    def test_submit_multinode(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()
        self.assertEqual('bar', testjob.name)
        self.assertIsNotNone(testjob.job_id)

    @lava_test
    def test_fetch_basics(self):
        testjob = TestJob(
            job_id='3',
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.fetch(testjob.id)
        testjob.refresh_from_db()
        self.assertEqual(True, testjob.fetched)

    @lava_test
    def test_fetch_not_finished(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()

        self.backend.fetch(testjob.id)
        testjob.refresh_from_db()
        self.assertEqual(False, testjob.fetched)
        self.assertEqual(0, testjob.fetch_attempts)


class RealLavaRESTTest(TestCase):

    def setUp(self):
        self.backend = Backend.objects.create(
            url='http://localhost/api/v0.2/',
            username='squadtest',
            token='kz8wyxmldwahe4w4086ceadedfwd0z7tadr87i60u1z30xymq38xy35ji98f0h6fgqmpwr3161zq87dytza70iqyhx5ab6xrzgh5lp1ghbcbrb0q650x8tpkgrm0a9n7',
            implementation_type='lava',
            backend_settings='',
        )
        self.group = Group.objects.create(
            name="group_foo"
        )
        self.project = Project.objects.create(
            name="project_foo",
            group=self.group,
        )
        self.build = self.project.builds.create(version='1')

    @lava_test
    def test_submit(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()
        self.assertEqual('bar', testjob.name)
        self.assertIsNotNone(testjob.job_id)

    @lava_test
    def test_submit_multinode(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()
        self.assertEqual('bar', testjob.name)
        self.assertIsNotNone(testjob.job_id)

    @lava_test
    def test_fetch_basics(self):
        testjob = TestJob(
            job_id='2',
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.fetch(testjob.id)
        testjob.refresh_from_db()
        self.assertEqual(True, testjob.fetched)

    @lava_test
    def test_fetch_not_finished(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()

        self.backend.fetch(testjob.id)
        testjob.refresh_from_db()
        self.assertEqual(False, testjob.fetched)
        self.assertEqual(0, testjob.fetch_attempts)

    @lava_test
    def test_cancel(self):
        testjob = TestJob(
            definition=QEMU_JOB_DEFINITION,
            target=self.project,
            target_build=self.build,
            environment="qemu",
            backend=self.backend)
        testjob.save()
        self.backend.submit(testjob)
        testjob.refresh_from_db()

        testjob.cancel()
        self.backend.fetch(testjob.id)
        testjob.refresh_from_db()
        self.assertEqual(True, testjob.fetched)
        self.assertEqual(0, testjob.fetch_attempts)
