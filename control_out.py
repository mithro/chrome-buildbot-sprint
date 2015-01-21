#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import getpass
import subprocess
import sys

USE_LOCAL_CACHE = True
BUILD_PLATFORM="linux"
BOOT_DISK_TYPE = 'pd-ssd'
GCE_PROJECT = 'delta-trees-830'
GCE_PROJECT_FLAG = '--project=%s' % GCE_PROJECT
GCE_ZONE = 'us-central1-a'
GCE_ZONE_FLAG = '--zone=%s' % GCE_ZONE

SHARED_COMMANDS = {
  'depot_tools_path': 'export PATH=~/chromium/depot_tools:"$PATH"',
}

import time
time_time_orig = time.time
def reltime(starttime=time_time_orig()):
  return time_time_orig() - starttime
time.time = reltime


def NoDash(string):
  return string.replace('-', '_')


# Basic wrapper around the gcloud commands
# --------------------------------------------------------

def GcloudCommand(args, suppress_zone=False):
  cmd = ['gcloud', 'compute'] + args + ['--project=%s' % GCE_PROJECT]
  if not suppress_zone:
    cmd += ['--zone=%s' % GCE_ZONE]
  print time.time(), 'GCE command:', ' '.join(cmd)
  return cmd

# Disk
def CreateDiskFromSnapshot(disk_name, snapshot_name):
  subprocess.check_call(GcloudCommand(['disks', 'create', disk_name,
                   '--source-snapshot', snapshot_name]))

def SnapshotDisk(disk_name, snapshot_name):
  subprocess.check_call(GcloudCommand(['disks', 'snapshot', disk_name,
                   '--snapshot-names', snapshot_name]))

def DeleteDisk(disk_name):
  subprocess.check_call(GcloudCommand(['disks', 'delete', disk_name,
                   '--quiet']))

def DiskExists(disk_name):
  if USE_LOCAL_CACHE:
    return disk_name in local_cached_disks
  return 0 == subprocess.call(GcloudCommand(['disks', 'describe', disk_name]), stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)

# Snapshots
def SnapshotReady(snapshot_name):
  if USE_LOCAL_CACHE:
    return snapshot_name in local_cached_ready_snapshots
  try:
    output = subprocess.check_output(GcloudCommand(['snapshots', 'describe', snapshot_name], suppress_zone=True), stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError:
    return False
  return "status: READY" in output


def DeleteSnapshot(snapshot_name):
  subprocess.check_call(GcloudCommand(['snapshots', 'delete', snapshot_name,
                   '--quiet'], suppress_zone=True))

# Instances
def RunCommandOnInstance(instance_name, command):
  subprocess.check_call(GcloudCommand(['ssh', 'ubuntu@' + instance_name,
                   '--command', command]))

def InstanceExists(instance_name):
  if USE_LOCAL_CACHE:
    return instance_name in local_cached_instances
  return 0 == subprocess.call(GcloudCommand(['instances', 'describe', instance_name]), stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)

def DeleteInstance(instance_name):
  subprocess.check_call(GcloudCommand(['instances', 'delete', instance_name,
                   '--quiet']))

def CreateInstanceWithDisks(instance_name, image_name, machine_type, disks):
  params = [
    'instances', 'create', instance_name,
    '--image=%s' % image_name,
    '--machine-type=%s' % machine_type,
    '--boot-disk-type=%s' % BOOT_DISK_TYPE,
  ]
  for disk in disks:
    params += ['--disk', 'mode='+disk.mode, 'name='+disk.name, 'device-name='+disk.name]
  subprocess.check_call(GcloudCommand(params))


def ShutdownInstance(instance_name):
  RunCommandOnInstance(instance_name, "sudo shutdown -h now")
  while True:
    output = subprocess.check_output(GcloudCommand(['instances', 'describe', instance_name]))
    if "status: RUNNING" not in output:
      break

# --------------------------------------------------------

def ImageName():
  return 'boot-image-wip'

# Naming
def DiskName(stage, commit, content):
  return '-'.join([NoDash(getpass.getuser()), 'disk', NoDash(BUILD_PLATFORM), NoDash(commit), stage, content])

def InstanceName(stage, commit):
  return '-'.join([NoDash(getpass.getuser()), 'instance', NoDash(BUILD_PLATFORM), NoDash(commit), stage])

def SnapshotName(commit, content):
  return '-'.join([NoDash(getpass.getuser()), 'snapshot', NoDash(BUILD_PLATFORM), NoDash(commit), content])


# --------------------------------------------------------

local_cached_instances = []
local_cached_disks = []
local_cached_ready_snapshots = []
def update_local_caches():
  print time.time(), 'Updading local caches'
  update_local_instances_cache()
  update_local_disks_cache()
  update_local_snapshots_cache()
  print time.time(), 'Local cache state:'
  print 'Instances:\n\t', '\n\t'.join(local_cached_instances)
  print 'Disks:\n\t', '\n\t'.join(local_cached_disks)
  print 'Ready Snapshots:\n\t', '\n\t'.join(local_cached_ready_snapshots)

def update_local_instances_cache():
  global local_cached_instances
  lines = [line.split() for line in subprocess.check_output(GcloudCommand(['instances', 'list'])).split('\n') if line]
  assert lines[0][0] == 'NAME'
  local_cached_instances = [line[0] for line in lines[1:]]

def update_local_disks_cache():
  global local_cached_disks
  lines = [line.split() for line in subprocess.check_output(GcloudCommand(['disks', 'list'])).split('\n') if line]
  assert lines[0][0] == 'NAME'
  local_cached_disks = [line[0] for line in lines[1:]]

def update_local_snapshots_cache():
  global local_cached_ready_snapshots
  lines = [line.split() for line in subprocess.check_output(GcloudCommand(['snapshots', 'list'], suppress_zone=True)).split('\n') if line]
  assert lines[0][0] == 'NAME'
  assert lines[0][3] == 'STATUS'
  local_cached_ready_snapshots = [line[0] for line in lines[1:] if line[3] == 'READY']

# --------------------------------------------------------

import cStringIO as StringIO
import collections
import threading
import traceback

class Disk(object):
  def log(self, s, *args):
    print time.time(), "%s(%s): disk(%s)" % (self.stage, self.commit_id, self.name), s % args

  def __init__(self, content, commit_id, stage, from_snapshot, mode="rw", save_snapshot=False):
    self.content = content
    self.commit_id = commit_id

    self.stage = stage
    self.from_snapshot = from_snapshot
    self.mode = mode
    self.save_snapshot = save_snapshot

  @property
  def name(self):
    return DiskName(self.stage, self.commit_id, self.content)  

  @property
  def snapshot_name(self):
    assert self.save_snapshot
    return SnapshotName(self.commit_id, self.content)

  @property
  def mnt(self):
    return {
      "src": "chromium",
      "out": "chromium/src/out",
    }[self.content]

  def exists(self):
    return DiskExists(self.name)

  def can_create(self):
    return SnapshotReady(self.from_snapshot)

  def create(self):
    self.log("creating disk")
    assert not self.exists()
    CreateDiskFromSnapshot(self.name, self.from_snapshot)
    self.log("created disk")

  def cleanup(self, clear_snapshot=False):
    if self.exists():
      DeleteDisk(self.name)
      self.log("deleted disk")

    if clear_snapshot and self.save_snapshot:
      if SnapshotReady(self.snapshot_name):
        DeleteSnapshot(self.snapshot_name)
        self.log("deleted snapshot %s", self.snapshot_name)

  def save(self):
    if self.save_snapshot:
      self.log("creating snapshot %s", self.snapshot_name)
      SnapshotDisk(self.name, self.snapshot_name)
      self.log("created snapshot %s", self.snapshot_name)

  def saved(self):
    if self.save_snapshot:
      return SnapshotReady(self.snapshot_name)
    return True


class Stage(threading.Thread):
  def log(self, s, *args):
    print time.time(), repr(self), s % args

  @classmethod
  def name(cls):
    return cls.__name__.lower()[:-len("stage")]

  def __init__(self, commit_id):
    threading.Thread.__init__(self)

    assert self.name() is not Stage.name()
    self.commit_id = commit_id
    self.instance_name = InstanceName(self.name(), self.commit_id)

  def __repr__(self):
    return "%s(%s)" % (self.name(), self.commit_id)

  def can_run(self):
    for disk in self.disks:
      if not disk.can_create():
        return False
    return True

  def done(self):
    for disk in self.disks:
      if not disk.saved():
        return False
    return True

  def run(self):
    self.log("running")

    # Check we are not already completed or currently running.
    assert not self.done()
    assert not InstanceExists(self.instance_name)

    disks = self.disks
    try:
      for disk in disks:
        disk.create()

      # Start up the instance and wait for it to be running.
      self.log("instance (%s) launching", self.instance_name)
      CreateInstanceWithDisks(self.instance_name, ImageName(), self.machine_type, disks)
      self.log("instance (%s) launched", self.instance_name)
      
      while True:
        try:
          RunCommandOnInstance(self.instance_name, "true")
          break
        except subprocess.CalledProcessError:
          time.sleep(0.5)

      self.log("instance (%s) running", self.instance_name)

      # Mount the disks into the VM
      cmd = ""
      for disk in disks:
        cmd += """\
mkdir -p %(mnt)s; \
sudo mount /dev/disk/by-id/google-%(name)s %(mnt)s; \
""" % {"name": disk.name, "mnt": disk.mnt}
      RunCommandOnInstance(self.instance_name, cmd)
      self.log("disks mounted")

      # Running the actual work command
      self.log("command commence")
      self.command()
      self.log("command complete")

      # Shutdown instance
      ShutdownInstance(self.instance_name)
      self.log("instance (%s) terminated", self.instance_name)

      # Create snapshot
      for disk in disks:
        disk.save()
      self.log("disks saved")

    except Exception, e:
      tb = StringIO.StringIO()
      traceback.print_exc(file=tb)
      self.log("Exception: %s", e)
      self.log(tb.getvalue())
      sys.exit(1)

    self.log("finalizing")
    # Delete instance
    if InstanceExists(self.instance_name):
      DeleteInstance(self.instance_name)
      self.log("instance (%s) deleted", self.instance_name)

    # Cleanup disks
    for disk in disks:
      disk.cleanup()
    self.log("disks deleted")


class SyncStage(Stage):
  def __init__(self, commit_id, sync_from):
    Stage.__init__(self, commit_id)
    self.sync_from = sync_from

  @property
  def machine_type(self):
    return 'n1-standard-2'

  @property
  def disks(self):
    return [
      Disk(
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=self.sync_from,
        save_snapshot=True,
      )
    ]

  def command(self):
    RunCommandOnInstance(self.instance_name, ' && '.join([
      SHARED_COMMANDS['depot_tools_path'],
      'cd chromium/src',
      'time gclient sync -r ' + self.commit_id,
    ]))


class BuildStage(Stage):
  def __init__(self, commit_id, build_from):
    Stage.__init__(self, commit_id)
    self.build_from = build_from

  @property
  def machine_type(self):
    return 'n1-standard-16'

  @property
  def disks(self):
    return [
      # Figure out the src for this commit
      Disk(
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=SnapshotName(self.commit_id, "src"),
        mode="ro",
      ),

      # Create the disk we'll use to generate the snapshot onto.
      Disk(
        content="out",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=self.build_from,
        save_snapshot=True,
      ),
    ]

  def command(self):
    RunCommandOnInstance(self.instance_name, ' && '.join([
      SHARED_COMMANDS['depot_tools_path'],
      'cd chromium/src',
      'time build/gyp_chromium',
      'time ninja -C out/Debug',
    ]))


if __name__ == "__main__":
  latest_commit_id = 'dcb7bf1cd13d2bd5'
  test_commit_ids = [
    'fa1651193bf94120',
    '32cbfaa6478f66b9',
    '1874cd207f996341',
  ]
  latest_sync_snapshot = SnapshotName(latest_commit_id, "src")
  latest_build_snapshot = SnapshotName(latest_commit_id, "out")

  update_local_caches()
  assert SnapshotReady(latest_sync_snapshot), "%s doesn't exist" % latest_sync_snapshot
  assert SnapshotReady(latest_build_snapshot), "%s doesn't exist" % latest_build_snapshot

  stages = []
  for c in test_commit_ids:
    stages.append(SyncStage(c, sync_from=latest_sync_snapshot))
    stages.append(BuildStage(c, build_from=latest_build_snapshot))
    latest_sync_snapshot = SnapshotName(c, "src")

  print "---"
  print "---"

  for s in stages:
    print "Cleaning up", s
    # Cleanup any leftover instances
    if InstanceExists(s.instance_name):
      print time.time(), "Deleting old instance %s" % s.instance_name
      DeleteInstance(s.instance_name)

    # Clean up any leftover disks from previous runs.
    for disk in s.disks:
      disk.cleanup(clear_snapshot=True)

  print "---"
  print "---"

  update_local_caches()
  for s in stages:
    print s, s.can_run(), s.done()

  print "---"
  print "---"

  raw_input("Run things? [Y/y]")

  while stages:
    print time.time(), 'Main loop iteration'

    update_local_caches()
    finished_stages = [s for s in stages if s.done()]
    if finished_stages:
      print time.time(), "Finished", finished_stages
      stages = [s for s in stages if not s in finished_stages]

    for stage in stages:
      if stage.can_run() and not stage.is_alive():
        if not stage.done():
          print time.time(), "Starting", stage
          stage.start()

      if stage.is_alive():
        print time.time(), "Currently running", stage

    time.sleep(60)
