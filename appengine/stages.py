#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import getpass

from tasklets import *
from helpers import *


class Stage(object):
  @property
  def stage_id(self):
    return '-'.join([NoDash(getpass.getuser()), self.current_commit, "linux", self.__class__.__name__.lower().replace('stage', '')])

  def __init__(self, previous_commit, current_commit):
    self.current_commit = current_commit
    self.previous_commit = previous_commit


class SyncStage(Stage):

  def tasklets(self):
    sid = self.stage_id

    previous_snap_src = Snapshot(SnapshotName(self.previous_commit, "src"))

    instance = Instance("%s-instance" % sid)
    disk_src = Disk("%s-disk-src" % sid)
    snap_src = Snapshot(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(sid+"-instance-create", instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-src-create", previous_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(sid+"-disk-src-attach", instance, disk_src))
    tasks.append(MountDisksInInstance(sid+"-disk-mount", instance, [(disk_src, "/mnt")]))

    run_task = RunCommandOnInstance(sid+"-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time gclient sync -r %s
""")
    tasks.append(run_task)

    umount_task = UnmountDisksInInstance(sid+"-disk-umount", instance, disk_src)
    tasks.append(WaitOnOtherTasks(umount_task, [run_task]))

    detach_task = DetachDiskFromInstance(sid+"-disk-src-detach", instance, disk_src)
    tasks.append(WaitOnOtherTasks(detach_task, [umount_task]))

    snapshot_task = CreateSnapshotFromDisk(sid+"-disk-src-snapshot", disk_src, snap_src)
    tasks.append(WaitOnOtherTasks(snapshot_task, [detach_task]))

    return tasks


class BuildStage(Stage):
  def tasklets(self):
    sid = self.stage_id

    current_snap_src = Snapshot(SnapshotName(self.current_commit, "src"))
    previous_snap_out = Snapshot(SnapshotName(self.previous_commit, "out"))

    instance = Instance("%s-instance" % sid)
    disk_src = Disk("%s-disk-src" % sid)
    disk_out = Disk("%s-disk-out" % sid)
    snap_out = Snapshot(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(sid+"-instance-create", instance, required_snapshots=[current_snap_src, previous_snap_out]))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-src-create", current_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(sid+"-disk-src-attach", instance, disk_src))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-out-create", previous_snap_out, disk_out))
    tasks.append(AttachDiskToInstance(sid+"-disk-out-attach", instance, disk_out))
    tasks.append(MountDisksInInstance(sid+"-disk-mount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")]))

    run_task = RunCommandOnInstance(sid+"-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time build/gyp_chromium;
time ninja -C out/Debug;
""")
    tasks.append(run_task)

    umount_task = UnmountDisksInInstance(sid+"-disk-umount", instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")])
    tasks.append(WaitOnOtherTasks(umount_task, [run_task]))

    detach_src_task = DetachDiskFromInstance(sid+"-disk-src-detach", instance, disk_src)
    tasks.append(WaitOnOtherTasks(detach_src_task, [umount_task]))

    detach_out_task = DetachDiskFromInstance(sid+"-disk-out-detach", instance, disk_out)
    tasks.append(WaitOnOtherTasks(detach_out_task, [umount_task]))

    snapshot_out_task = CreateSnapshotFromDisk(sid+"-disk-out-snapshot", disk_out, snap_out)
    tasks.append(WaitOnOtherTasks(snapshot_out_task, [detach_out_task]))

    return tasks


if __name__ == "__main__":
  previous_commit = "commit0"
  current_commit = "commit1"

  import libcloud_gae
  driver = libcloud_gae.new_driver()

  print "SyncStage"
  print "-"*80
  for t in SyncStage(previous_commit, current_commit).tasklets():
    print t
    print ('startable', t.is_startable(driver)), ('running', t.is_running(driver)), ('done', t.is_finished(driver))
    print

  print "-"*80
  print
  print "BuildStage"
  print "-"*80
  for t in BuildStage(previous_commit, current_commit).tasklets():
    print t
  print "-"*80
