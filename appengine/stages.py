#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

from __future__ import print_function

import getpass

from tasklets import *
from helpers import *


class Stage(object):
  @property
  def stage_id(self):
    return '-'.join([NoDash(getpass.getuser()), 'new', self.current_commit, "linux", self.__class__.__name__.lower().replace('stage', '')])

  def __init__(self, previous_commit, current_commit):
    self.current_commit = current_commit
    self.previous_commit = previous_commit


class SyncStage(Stage):

  def tasklets(self):
    sid = self.stage_id

    previous_snap_src = Snapshot.load(SnapshotName(self.previous_commit, "src"))

    instance = Instance.load("%s-instance" % sid)
    disk_src = Disk.load("%s-disk-src" % sid)
    snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(sid+"-instance-create", instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-src-create", previous_snap_src, disk_src))
    mount_task = MountDisksInInstance(sid+"-disk-mount", instance, [(disk_src, "/mnt/chromium")])
    attach_task = CancelledByOtherTask(
        AttachDiskToInstance(sid+"-disk-src-attach", instance, disk_src, 'READ_WRITE'),
        mount_task)
    tasks.append(attach_task)
    tasks.append(mount_task)

    run_task = WaitOnOtherTasks(
        RunCommandOnInstance(sid+"-run", instance, ";".join(("""\
export PATH=$PATH:/mnt/chromium/depot_tools
cd /mnt/chromium/src
time gclient sync -r %s
""" % self.current_commit).split('\n'))),
        [mount_task])
    tasks.append(run_task)

    umount_task = WaitOnOtherTasks(
        UnmountDisksInInstance(sid+"-disk-umount", instance, [(disk_src, '/mnt/chromium')]),
        [run_task])
    tasks.append(umount_task)

    detach_task = WaitOnOtherTasks(
        DetachDiskFromInstance(sid+"-disk-src-detach", instance, disk_src),
        [umount_task])
    tasks.append(detach_task)

    snapshot_task = WaitOnOtherTasks(
        CreateSnapshotFromDisk(sid+"-disk-src-snapshot", disk_src, snap_src),
        [detach_task])
    tasks.append(snapshot_task)

    return tasks


class BuildStage(Stage):
  def tasklets(self):
    sid = self.stage_id

    current_snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))
    previous_snap_out = Snapshot.load(SnapshotName(self.previous_commit, "out"))

    instance = Instance.load("%s-instance" % sid)
    disk_src = Disk.load("%s-disk-src" % sid)
    disk_out = Disk.load("%s-disk-out" % sid)
    snap_out = Snapshot.load(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(sid+"-instance-create", instance, required_snapshots=[current_snap_src, previous_snap_out]))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-src-create", current_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(sid+"-disk-src-attach", instance, disk_src, 'READ_ONLY'))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-out-create", previous_snap_out, disk_out))
    tasks.append(AttachDiskToInstance(sid+"-disk-out-attach", instance, disk_out, 'READ_WRITE'))

    mount_task = MountDisksInInstance(sid+"-disk-mount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")])
    tasks.append(mount_task)

    run_task = RunCommandOnInstance(sid+"-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time build/gyp_chromium;
time ninja -C out/Debug;
""")
    tasks.append(WaitOnOtherTasks(run_task, [mount_task]))

    umount_task = WaitOnOtherTasks(
      UnmountDisksInInstance(sid+"-disk-umount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")]),
      [run_task])
    tasks.append(unmount_task)

    detach_src_task = WaitOnOtherTasks(
      DetachDiskFromInstance(sid+"-disk-src-detach", instance, disk_src),
      [umount_task])
    tasks.append(detach_src_task)

    detach_out_task = WaitOnOtherTasks(
      DetachDiskFromInstance(sid+"-disk-out-detach", instance, disk_out),
      [umount_task])
    tasks.append(detach_out_task)

    snapshot_out_task = WaitOnOtherTasks(
      CreateSnapshotFromDisk(sid+"-disk-out-snapshot", disk_out, snap_out),
      [detach_out_task])
    tasks.append(snapshot_out_task)

    return tasks


