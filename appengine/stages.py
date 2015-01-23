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

    previous_snap_src = Snapshot.load(SnapshotName(self.previous_commit, "src"))

    instance = Instance.load("%s-instance" % sid)
    disk_src = Disk.load("%s-disk-src" % sid)
    snap_src = Snapshot.load(SnapshotName(self.current_commit, "src"))

    tasks = []
    tasks.append(CreateInstance(sid+"-instance-create", instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(sid+"-disk-src-create", previous_snap_src, disk_src))
    tasks.append(AttachDiskToInstance(sid+"-disk-src-attach", instance, disk_src))
    tasks.append(MountDisksInInstance(sid+"-disk-mount", instance, [(disk_src, "/mnt")]))

    run_task = RunCommandOnInstance(sid+"-run", instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time gclient sync -r %s
""" % self.current_commit)
    tasks.append(run_task)

    umount_task = UnmountDisksInInstance(sid+"-disk-umount", instance, [(disk_src, '/mnt/chromium')])
    tasks.append(WaitOnOtherTasks(umount_task, [run_task]))

    detach_task = DetachDiskFromInstance(sid+"-disk-src-detach", instance, disk_src)
    tasks.append(WaitOnOtherTasks(detach_task, [umount_task]))

    snapshot_task = CreateSnapshotFromDisk(sid+"-disk-src-snapshot", disk_src, snap_src)
    tasks.append(WaitOnOtherTasks(snapshot_task, [detach_task]))

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
  import libcloud_gae

  import threading
  import pprint
  class Updater(threading.Thread):
    def skip(self, obj):
      return not obj.name.startswith(NoDash(getpass.getuser()))

    def run(self):
      driver = libcloud_gae.new_driver()
    
      while True:
        nodes = driver.list_nodes()
        volumes = driver.list_volumes()
        snapshots = driver.ex_list_snapshots()

        for node in nodes:
          if self.skip(node):
            continue
          Instance.load(node.name, gce_obj=node)

        for volume in volumes:
          if self.skip(node):
            continue
          Disk.load(volume.name, gce_obj=volume)

        for snapshot in snapshots:
          if self.skip(node):
            continue
          Snapshot.load(snapshot.name, gce_obj=snapshot)

        print "="*80+'\n', time.time(), "Finish updating gce\n", pprint.pformat(memcache), '\n'+"="*80+'\n'

        time.sleep(1)

  updater = Updater()
  updater.start()


  previous_commit = "commit0"
  current_commit = "commit1"

  driver = libcloud_gae.new_driver()

  print "SyncStage"
  print "-"*80
  for t in SyncStage(previous_commit, current_commit).tasklets():
    print t
    print ('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished())
    if isinstance(t, WaitOnOtherTasks):
      print "-->", t.task_to_run
      print "-->", ('startable', t.task_to_run.is_startable()), ('running', t.task_to_run.is_running()), ('done', t.task_to_run.is_finished())

    print

  print "-"*80
  print
  print "BuildStage"
  print "-"*80
  for t in BuildStage(previous_commit, current_commit).tasklets():
    print t
    print ('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished())
    print
  print "-"*80

  while updater.is_alive():
    for t in SyncStage(previous_commit, current_commit).tasklets():
      if t.is_startable():
        if t.is_running():
          print time.time(), t.tid, "running"
          continue

        if t.is_finished():
          print time.time(), t.tid, "finished"
          continue

        print time.time(), t.tid, "starting"
        t.run(driver)
        print time.time(), t.tid, "started"
      else:
        print time.time(), t.tid, "pending"

    print "-" * 80
    time.sleep(1)
