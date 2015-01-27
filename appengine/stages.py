#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

from __future__ import print_function

import getpass
try:
  from termcolor import cprint as print_color
except ImportError:
  def print_color(*args, **kw):
    print(*args, **kw)

from tasklets import *
from helpers import *

import sys
def info(type, value, tb):
  from libcloud.common.google import ResourceInUseError
  if hasattr(sys, 'ps1') or not sys.stderr.isatty() or isinstance(type, ResourceInUseError):
    # we are in interactive mode or we don't have a tty-like
    # device, so we call the default hook
    sys.__excepthook__(type, value, tb)
  else:
    import traceback, pdb
    # we are NOT in interactive mode, print the exception...
    traceback.print_exception(type, value, tb)
    print
    # ...then start the debugger in post-mortem mode.
    pdb.pm()

sys.excepthook = info





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


if __name__ == "__main__":
  previous_commit = "fa1651193bf94120"
  current_commit = "32cbfaa6478f66b9"

  import libcloud_gae
  driver = libcloud_gae.new_driver()
  starting_snap = Snapshot.load(SnapshotName(previous_commit, "src"), driver=driver)
  assert starting_snap.exists(), starting_snap.name

  import threading
  import pprint
  class Updater(threading.Thread):
    output = True
    ready = False
    go = True

    def skip(self, obj):
      return not obj.name.startswith(NoDash(getpass.getuser()) + '-new-')

    def run(self):
      driver = libcloud_gae.new_driver()
    
      old_nodes = []
      old_volumes = []
      old_snapshots = []
      while self.go:
        nodes = driver.list_nodes()
        volumes = driver.list_volumes()
        snapshots = driver.ex_list_snapshots()

        for node in nodes:
          if self.skip(node):
            continue
          Instance.load(node.name, gce_obj=node)

        for volume in volumes:
          if self.skip(volume):
            continue
          Disk.load(volume.name, gce_obj=volume)

        for snapshot in snapshots:
          if self.skip(snapshot):
            continue
          Snapshot.load(snapshot.name, gce_obj=snapshot)

        self.ready = True
        if self.output:
          if old_nodes != nodes or old_volumes != volumes or old_snapshots != snapshots:
            print("="*80+'\n', time.time(), "Finish updating gce\n", pprint.pformat(memcache), '\n'+"="*80+'\n')
          old_nodes = nodes
          old_volumes = volumes
          old_snapshots = snapshots

  updater = Updater()
  updater.start()
  while not updater.ready and updater.is_alive():
    time.sleep(1)

  print("SyncStage")
  print("-"*80)
  for t in SyncStage(previous_commit, current_commit).tasklets():
    print(t)
    print(('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished()))
    if isinstance(t, WaitOnOtherTasks):
      print("-->", t.task_to_run)
      print("-->", ('startable', t.task_to_run.is_startable()), ('running', t.task_to_run.is_running()), ('done', t.task_to_run.is_finished()))
    print


  try:
    updater.output = False
    raw_input("okay?")
    updater.output = True

    """
    print("-"*80)
    print
    print("BuildStage")
    print("-"*80)
    for t in BuildStage(previous_commit, current_commit).tasklets():
      print(t)
      print(('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished()))
      print
    print("-"*80)
    """

    while updater.is_alive():
      for t in SyncStage(previous_commit, current_commit).tasklets():
        print(time.time(), t.tid, ('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished()), end=' ')
        if t.is_startable():
          if t.is_running():
            print("running")
            continue

          if t.is_finished():
            print("finished")
            continue

          print_color("starting", color='green')
          updater.output = False
          raw_input("run?")
          updater.output = True
          def run(t=t):
            driver = libcloud_gae.new_driver()
            t.run(driver)
          threading.Thread(target=run).start()
        else:
          print("pending")

      print("-" * 80)
      time.sleep(1)
  finally:
    updater.go = False
    updater.join()
