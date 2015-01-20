#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import getpass
import subprocess

BUILD_PLATFORM="linux"


def NoDash(string):
  return string.replace('-', '_')


# Basic wrapper around the gcloud commands
# --------------------------------------------------------

# Disk
def CreateDiskFromSnapshot(disk_name, snapshot_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'create', disk_name,
                   '--source-snapshot', snapshot_name])

def SnapshotDisk(disk_name, snapshot_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'snapshot', disk_name,
                   '--snapshot-names', snapshot_name])

def DeleteDisk(disk_name):
  subprocess.call(['gcloud', 'compute', 'disks', 'delete', disk_name,
                   '--quiet'])

def DiskExists(disk_name):
  return 0 == subprocess.call(['gcloud', 'compute', 'disks', 'describe', disk_name], stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)

# Snapshots
def SnapshotReady(snapshot_name):
  try:
    output = subprocess.check_output(['gcloud', 'compute', 'snapshots', 'describe', snapshot_name], stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError:
    return False
  return "status: READY" in output
  #return 0 == subprocess.call(, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)


def DeleteSnapshot(snapshot_name):
  subprocess.call(['gcloud', 'compute', 'snapshots', 'delete', snapshot_name,
                   '--quiet'])

# Instances
def RunCommandOnInstance(instance_name, command):
  return subprocess.call(['gcloud', 'compute', 'ssh', instance_name,
                   '--command', command])

def InstanceExists(instance_name):
  return 0 == subprocess.call(['gcloud', 'compute', 'instances', 'describe', instance_name], stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)

def DeleteInstance(instance_name):
  subprocess.call(['gcloud', 'compute', 'instances', 'delete', instance_name,
                   '--quiet'])

def CreateInstanceWithDisks(instance_name, image_name, disks):
  params = ['gcloud', 'compute', 'instances', 'create', instance_name,
            '--image', image_name]
  for name, mode, mnt in disks:
    params += ['--disk', 'mode='+mode, 'name='+name, 'device-name='+name]
  subprocess.call(params)


def ShutdownInstance(instance_name):
  RunCommandOnInstance(instance_name, "sudo shutdown -h now")
  while True:
    output = subprocess.check_output(['gcloud', 'compute', 'instances', 'describe', instance_name])
    if "status: RUNNING" not in output:
      break

# --------------------------------------------------------

def ImageName():
  return 'ubuntu-14-04'

# Naming
def DiskName(stage, commit):
  return '-'.join([NoDash(getpass.getuser()), 'disk', NoDash(BUILD_PLATFORM), NoDash(commit), stage])

def InstanceName(stage, commit):
  return '-'.join([NoDash(getpass.getuser()), 'instance', NoDash(BUILD_PLATFORM), NoDash(commit), stage])

def SnapshotName(stage, commit):
  return '-'.join([NoDash(getpass.getuser()), 'snapshot', NoDash(BUILD_PLATFORM), NoDash(commit), stage])


# --------------------------------------------------------

import time
import collections
import threading

Disk = collections.namedtuple("Disk", ["name","mode","mnt"])


class Stage(threading.Thread):
  def __init__(self, commit_id, wait_for_stage=None):
    threading.Thread.__init__(self)

    assert self.STAGE is not None
    self.commit_id = commit_id
    self.result_name = SnapshotName(self.STAGE, self.commit_id)
    self.instance_name = InstanceName(self.STAGE, self.commit_id)

    self.disks = []
    self.disk_result = None

    self.wait_for_stage = wait_for_stage

  def __repr__(self):
    return "%s(%s %s)" % (self.__class__.__name__, self.commit_id, self.wait_for_stage)

  def can_run(self):
    return (not self.wait_for_stage) or self.wait_for_stage.done()

  def done(self):
    return SnapshotReady(self.result_name)

  def run(self):
    assert self.wait_for_stage.done()
    self.setup_disks()

    assert self.disks
    assert self.disk_result

    assert not SnapshotReady(self.result_name)
    assert not InstanceExists(self.instance_name)
    CreateInstanceWithDisks(self.instance_name, ImageName(), self.disks)

    print time.time(), "%s: Created" % self.instance_name

    while True:
      if RunCommandOnInstance(self.instance_name, "true") == 0:
        break
      time.sleep(0.5)

    print time.time(), "%s: Running" % self.instance_name

    cmd = ""
    for disk in self.disks:
      cmd += """\
sudo mkdir -p %(mnt)s; \
sudo mount /dev/disk/by-id/google-%(name)s %(mnt)s; \
sudo chmod a+rw %(mnt)s; \
""" % disk.__dict__
    print time.time(), cmd
    RunCommandOnInstance(self.instance_name, cmd)

    print time.time(), "%s: Mounted" % self.instance_name

    self.command()

    print time.time(), "%s: Command finished" % self.instance_name

    # Shutdown instance
    ShutdownInstance(self.instance_name)

    print time.time(), "%s: Shutdowned" % self.instance_name

    # Create snapshot
    SnapshotDisk(self.disk_result, self.result_name)

    print time.time(), "%s: Snapshotted" % self.instance_name

    # Delete instance
    DeleteInstance(self.instance_name)

    print time.time(), "%s: Deleted" % self.instance_name


class SyncStage(Stage):
  STAGE = "src"

  def setup_disks(self):
    # Create the disk we'll use to generate the snapshot onto.
    self.disk_result = DiskName("src", self.commit_id)
    CreateDiskFromSnapshot(self.disk_result, self.wait_for_stage.result_name)
    self.disks.append(Disk(name=self.disk_result, mode="rw", mnt="/mnt/disk"))

  def command(self):
    RunCommandOnInstance(self.instance_name, "sleep 60")


class BuildStage(Stage):
  STAGE = "out"

  def __init__(self, commit_id, wait_for_stage=None, build_from=None):
    Stage.__init__(self, commit_id, wait_for_stage)
    self.build_from = build_from

  def setup_disks(self):
    # Figure out the src for this commit
    self.disk_src = DiskName("src", self.commit_id)
    self.disks.append(Disk(name=self.disk_src, mode="ro", mnt="/mnt/disk"))

    # Create the disk we'll use to generate the snapshot onto.
    assert SnapshotReady(self.build_from)
    self.disk_result = DiskName("out", self.commit_id)
    CreateDiskFromSnapshot(self.disk_result, self.build_from)
    self.disks.append(Disk(name=self.disk_result, mode="rw", mnt="/mnt/disk/chromium/src/out"))

  def command(self):
    RunCommandOnInstance(self.instance_name, "sleep 600")


if __name__ == "__main__":
  # Check t0 base snapshots exist
  assert DiskExists(DiskName("src", "commit1"))
  assert SnapshotReady(SnapshotName("src", "commit1"))
  build_start = SnapshotName("out", "commit0")
  assert SnapshotReady(build_start), "Snapshot %s doesn't exist" % build_start

  commits = ["commit1", "commit2", "commit3"]

  last_sync = None

  stages = []
  for c in commits:
    sync = SyncStage(c, last_sync)
    build = BuildStage(c, sync, build_from=build_start)

    stages.append(sync)
    stages.append(build)

    last_sync = sync

  print "---"
  for s in stages:
    print s, s.can_run()
  print "---"

  raw_input("Run things? [y]")

  while stages:
    finished_stages = [s for s in stages if s.done()]
    print time.time(), "Finished", finished_stages
    stages = [s for s in stages if not s in finished_stages]

    for stage in stages:
      if stage.can_run() and not stage.is_alive():
        if not stage.done():
          print time.time(), "Starting", stage
          stage.start()

    time.sleep(1)
