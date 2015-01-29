#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

from __future__ import print_function

import getpass

from helpers import Namespace
from objects import (
  Snapshot,
  SnapshotName,
  Instance,
  Disk,
)
from tasklets import (
  CreateInstance,
  CreateDiskFromSnapshot,
  MountDisksInInstance,
  CancelledByOtherTask,
  AttachDiskToInstance,
  WaitOnOtherTasks,
  RunCommandOnInstance,
  UnmountDisksInInstance,
  DetachDiskFromInstance,
  CreateSnapshotFromDisk,
)


class Stage(object):
  @property
  def stage_id(self):
    return '-'.join([
      Namespace(),
      self.current_commit,
      "win",
      self.name,
    ])

  def __init__(self, previous_commit, current_commit):
    self.current_commit = current_commit
    self.previous_commit = previous_commit
    self._inputs = []
    self._outputs = []
    self._objects = []
    self.tasklets = self._tasklets()

  @property
  def name(self):
    return self.__class__.__name__.replace('Stage', '').lower()

  def _tasklets(self):
    raise NotImplementedError()

  def inputs(self):
    return self._inputs

  def outputs(self):
    return self._outputs

  def objects(self):
    return self._objects

  def cleanup(self, driver):
    for o in self.objects():
        if o.exists():
            o.destroy(driver)

  def needs_cleanup(self):
    if self.is_finished():
      for o in self.objects():
        if o.exists():
          return True
    else:
      for o in self.objects():
        if o.status == "TERMINATED":
          return True
    return False

  def is_finished(self):
    return all(o.ready() for o in self.outputs())


class SyncStage(Stage):

  def _tasklets(self):
    sid = self.stage_id

    previous_snap_src = Snapshot.load(SnapshotName(self.previous_commit, "src"))
    self._inputs.append(previous_snap_src)

    instance = Instance.load("%s-instance" % sid)
    self._objects.append(instance)
    disk_src = Disk.load("%s-disk-src" % sid)
    self._objects.append(disk_src)

    snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))
    self._outputs.append(snap_src)

    tasks = []
    tasks.append(CreateInstance(self, sid + "-instance-create", instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(self, sid + "-disk-src-create", previous_snap_src, disk_src))
    mount_task = MountDisksInInstance(self, sid + "-disk-mount", instance, [(disk_src, "/mnt/chromium")])
    attach_task = CancelledByOtherTask(
        AttachDiskToInstance(self, sid + "-disk-src-attach", instance, disk_src, 'READ_WRITE'),
        mount_task)
    tasks.append(attach_task)
    tasks.append(mount_task)

    run_task = WaitOnOtherTasks(
        RunCommandOnInstance(self, sid+"-run", instance,
          "gclient sync -r %s" % self.current_commit,
          cwd='/mnt/chromium/src',
          user='ubuntu'),
        [mount_task])
    tasks.append(run_task)

    umount_task = WaitOnOtherTasks(
        UnmountDisksInInstance(self, sid + "-disk-umount", instance, [(disk_src, '/mnt/chromium')]),
        [run_task])
    tasks.append(umount_task)

    detach_task = WaitOnOtherTasks(
        DetachDiskFromInstance(self, sid + "-disk-src-detach", instance, disk_src),
        [umount_task])
    tasks.append(detach_task)

    snapshot_task = WaitOnOtherTasks(
        CreateSnapshotFromDisk(self, sid + "-disk-src-snapshot", disk_src, snap_src),
        [detach_task])
    tasks.append(snapshot_task)

    return tasks


class BuildStage(Stage):
  def _tasklets(self):
    sid = self.stage_id

    current_snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))
    previous_snap_out = Snapshot.load(SnapshotName(self.previous_commit, "out"))

    instance = Instance.load("%s-instance" % sid)
    disk_src = Disk.load("%s-disk-src" % sid)
    disk_out = Disk.load("%s-disk-out" % sid)
    snap_out = Snapshot.load(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(self, sid + "-instance-create", instance, required_snapshots=[current_snap_src, previous_snap_out]))
    tasks.append(CreateDiskFromSnapshot(self, sid + "-disk-src-create", current_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(self, sid + "-disk-src-attach", instance, disk_src, 'READ_ONLY'))
    tasks.append(CreateDiskFromSnapshot(self, sid + "-disk-out-create", previous_snap_out, disk_out))
    tasks.append(AttachDiskToInstance(self, sid + "-disk-out-attach", instance, disk_out, 'READ_WRITE'))

    mount_task = MountDisksInInstance(self, sid + "-disk-mount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")])
    tasks.append(mount_task)

    run_task = RunCommandOnInstance(self, sid + "-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time build/gyp_chromium;
time ninja -C out/Debug;
""")
    tasks.append(WaitOnOtherTasks(run_task, [mount_task]))

    umount_task = WaitOnOtherTasks(
      UnmountDisksInInstance(self, sid + "-disk-umount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")]),
      [run_task])
    tasks.append(umount_task)

    detach_src_task = WaitOnOtherTasks(
      DetachDiskFromInstance(self, sid + "-disk-src-detach", instance, disk_src),
      [umount_task])
    tasks.append(detach_src_task)

    detach_out_task = WaitOnOtherTasks(
      DetachDiskFromInstance(self, sid + "-disk-out-detach", instance, disk_out),
      [umount_task])
    tasks.append(detach_out_task)

    snapshot_out_task = WaitOnOtherTasks(
      CreateSnapshotFromDisk(self, sid + "-disk-out-snapshot", disk_out, snap_out),
      [detach_out_task])
    tasks.append(snapshot_out_task)

    return tasks


from google.appengine.ext import db
from db_objects import TestResults

class TestResultsUploadedObject:
  def __init__(self, path):
    self._path = path

  def ready(self):
    return TestResults.get_by_key_name(self._path) != None

class TestStage(Stage):
  TEST_BINARY = 'unit_tests'
  TOTAL_SHARDS = 1
  SHARD_INDEX = 0

  def _tasklets(self):
    sid = self.stage_id

    self._inputs = []
    self._outputs = [TestResultsUploadedObject(sid)]
    self._objects = []

    current_snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))
    self._inputs.append(current_snap_src)
    current_snap_out = Snapshot.load(SnapshotName(self.current_commit, "out"))
    self._inputs.append(current_snap_out)

    instance = Instance.load("%s-instance" % sid)
    self._objects.append(instance)
    disk_src = Disk.load("%s-disk-src" % sid)
    self._objects.append(disk_src)
    disk_out = Disk.load("%s-disk-out" % sid)
    self._objects.append(disk_out)

    tasks = []
    tasks.append(CreateInstance(self, sid + "-instance-create", instance, required_snapshots=[current_snap_src, current_snap_out]))
    tasks.append(CreateDiskFromSnapshot(self, sid + "-disk-src-create", current_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(self, sid + "-disk-src-attach", instance, disk_src, 'READ_ONLY'))
    tasks.append(CreateDiskFromSnapshot(self, sid + "-disk-out-create", current_snap_out, disk_out))
    tasks.append(AttachDiskToInstance(self, sid + "-disk-out-attach", instance, disk_out, 'READ_ONLY'))

    mount_task = MountDisksInInstance(self, sid + "-disk-mount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")])
    tasks.append(mount_task)

    shard_variables = ('GTEST_TOTAL_SHARDS=%(total)d GTEST_SHARD_INDEX=%(index)d '
                       % {'total': self.TOTAL_SHARDS, 'index': self.SHARD_INDEX})
    xvfb_command = 'xvfb-run --server-args=\'-screen 0, 1024x768x24\' '
    command = (shard_variables + xvfb_command +
       ('out/Debug/%(test_binary)s --gtest_output="xml:/tmp/%(test_binary)s.xml"'
        % {'test_binary': self.TEST_BINARY}))

    run_task = WaitOnOtherTasks(RunCommandOnInstance(self, sid + "-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
sudo apt-get install xvfb -y;
chromium/src/build/update-linux-sandbox.sh;
export CHROME_DEVEL_SANDBOX=/usr/local/sbin/chrome-devel-sandbox;
time %(command)s;
""" % { 'command': command}), [mount_task])
    tasks.append(run_task)

    upload_results_task = WaitOnOtherTasks(RunCommandOnInstance(self, sid + "-upload-results", instance, """\
curl -d @/tmp/%(test_binary)s.xml -X POST http://delta-trees-830.appspot.com/test_results/%(test_run_id)s
""" % { 'test_binary': self.TEST_BINARY, 'test_run_id': sid}), [run_task])
    tasks.append(upload_results_task)

    umount_task = WaitOnOtherTasks(
      UnmountDisksInInstance(self, sid + "-disk-umount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")]),
      [run_task])
    tasks.append(umount_task)

    detach_src_task = WaitOnOtherTasks(
      DetachDiskFromInstance(self, sid + "-disk-src-detach", instance, disk_src),
      [umount_task])
    tasks.append(detach_src_task)

    detach_out_task = WaitOnOtherTasks(
      DetachDiskFromInstance(self, sid + "-disk-out-detach", instance, disk_out),
      [umount_task])
    tasks.append(detach_out_task)

    return tasks
