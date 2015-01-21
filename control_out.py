#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import getpass
import subprocess

MACHINE_SIZE = 'n1-standard-1'
BUILD_PLATFORM = "linux"

import time
time_time_orig = time.time
def reltime(starttime=time_time_orig()):
  return time_time_orig() - starttime
time.time = reltime


def NoDash(string):
  return string.replace('-', '_')


# Basic wrapper around the gcloud commands
# --------------------------------------------------------

from libcloud.common.google import ResourceNotFoundError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.ssh import ParamikoSSHClient as SSHClient

PROJECT_ID = 'delta-trees-830'
REGION = 'us-central1'
ZONE = 'us-central1-a'

SERVICE_ACCOUNT_EMAIL = '621016184110-tpkj4skaep6c8ccgolhoheepffasa9kq@developer.gserviceaccount.com'
SERVICE_ACCOUNT_KEY_PATH = '../chrome-buildbot-sprint-c514ee5826d1.pem'
SCOPES = ['https://www.googleapis.com/auth/compute']

SSH_KEY_PATH = '../gce_bot_rsa'
STARTUP_SCRIPT = 'startup_script.sh'

ComputeEngine = get_driver(Provider.GCE)
DRIVER = ComputeEngine(SERVICE_ACCOUNT_EMAIL,
                       SERVICE_ACCOUNT_KEY_PATH,
                       datacenter=ZONE,
                       project=PROJECT_ID,
                       auth_type='SA',
                       scopes=SCOPES)

# Snapshots
def SnapshotReady(driver, snapshot_name):
  try:
    driver.ex_get_snapshot(snapshot_name)
    return True
  except ResourceNotFoundError:
    return False

# Instances
def RunCommandOnInstance(instance_name, command):
  node = DRIVER.ex_get_node(instance_name)
  ssh = SSHClient(node.public_ips[0], username='ubuntu', key=SSH_KEY_PATH)
  ssh.connect()
  stdout, stderr, returncode = ssh.run(command)
  ssh.close()
  if returncode != 0:
    raise subprocess.CalledProcessError(returncode, command, stdout + stderr)

def InstanceExists(instance_name):
  try:
    DRIVER.ex_get_node(instance_name)
    return True
  except ResourceNotFoundError:
    return False

def DeleteInstance(instance_name):
  DRIVER.destroy_node(DRIVER.ex_get_node(instance_name))

def CreateInstanceWithDisks(instance_name, image_name, disks=[]):
  node = DRIVER.deploy_node(instance_name, size=MACHINE_SIZE, image=image_name, script=STARTUP_SCRIPT)
  for disk in disks:
    DRIVER.attach_volume(node, DRIVER.ex_get_volume(disk.name), disk.name, disk.mode)

def ShutdownInstance(instance_name):
  RunCommandOnInstance(instance_name, "sudo shutdown -h now")
  try:
    while DRIVER.ex_get_node(instance_name).state == 'RUNNING':
      pass
  except ResourceNotFoundError:
    pass

# --------------------------------------------------------

def ImageName():
  return 'ubuntu-14-04'

# Naming
def DiskName(stage, commit, content):
  return '-'.join([NoDash(getpass.getuser()), 'disk', NoDash(BUILD_PLATFORM), NoDash(commit), stage, content])

def InstanceName(stage, commit):
  return '-'.join([NoDash(getpass.getuser()), 'instance', NoDash(BUILD_PLATFORM), NoDash(commit), stage])

def SnapshotName(commit, content):
  return '-'.join([NoDash(getpass.getuser()), 'snapshot', NoDash(BUILD_PLATFORM), NoDash(commit), content])


# --------------------------------------------------------

import cStringIO as StringIO
import collections
import threading
import traceback

class Disk(object):
  def log(self, s, *args):
    print time.time(), "%s(%s): disk(%s)" % (self.stage, self.commit_id, self.name), s % args

  def __init__(self, driver, content, commit_id, stage, from_snapshot, mode="rw", save_snapshot=False):
    self.driver = driver

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
      "src": "/mnt/disk",
      "out": "/mnt/disk/chromium/src/out",
    }[self.content]

  def exists(self):
    return self.DiskExists(self.name)

  def can_create(self):
    return SnapshotReady(self.driver, self.from_snapshot)

  def create(self):
    self.log("creating disk")
    assert not self.exists()
    self.CreateDiskFromSnapshot(self.name, self.from_snapshot)
    self.log("created disk")

  def cleanup(self, clear_snapshot=False):
    if self.exists():
      self.DeleteDisk(self.name)
      self.log("deleted disk")

    if clear_snapshot and self.save_snapshot:
      if SnapshotReady(self.driver, self.snapshot_name):
        self.DeleteSnapshot(self.snapshot_name)
        self.log("deleted snapshot %s", self.snapshot_name)

  def save(self):
    if self.save_snapshot:
      self.log("creating snapshot %s", self.snapshot_name)
      self.SnapshotDisk(self.name, self.snapshot_name)
      self.log("created snapshot %s", self.snapshot_name)

  def saved(self):
    if self.save_snapshot:
      return SnapshotReady(self.driver, self.snapshot_name)
    return True

  def CreateDiskFromSnapshot(disk_name, snapshot_name):
    self.driver.create_volume(size=None, name=disk_name, snapshot=snapshot_name, ex_disk_type='pd-ssd')

  def SnapshotDisk(disk_name, snapshot_name):
    volume = self.driver.ex_get_volume(disk_name)
    self.driver.create_volume_snapshot(volume, snapshot_name)

  def DeleteDisk(disk_name):
    self.driver.destroy_volume(self.driver.ex_get_volume(disk_name))

  def DiskExists(disk_name):
    try:
      self.driver.ex_get_volume(disk_name)
      return True
    except ResourceNotFoundError:
      return False

  def DeleteSnapshot(snapshot_name):
    self.driver.destroy_volume_snapshot(DRIVER.ex_get_snapshot(snapshot_name))


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
    for disk in self.disks(DRIVER):
      if not disk.can_create():
        return False
    return True

  def done(self):
    for disk in self.disks(DRIVER):
      if not disk.saved():
        return False
    return True

  def run(self):
    self.log("running")

    # Check we are not already completed or currently running.
    assert not self.done()
    assert not InstanceExists(self.instance_name)

    disks = self.disks(DRIVER)
    try:
      for disk in disks:
        disk.create()

      # Start up the instance and wait for it to be running.
      self.log("instance (%s) launching", self.instance_name)
      CreateInstanceWithDisks(self.instance_name, ImageName(), disks)
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
sudo mkdir -p %(mnt)s; \
sudo mount /dev/disk/by-id/google-%(name)s %(mnt)s; \
sudo chmod a+rw %(mnt)s; \
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
      raise

    finally:
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

  def disks(self, driver):
    return [
      Disk(
        driver=driver,
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=self.sync_from,
        save_snapshot=True,
      )
    ]

  def command(self):
    RunCommandOnInstance(self.instance_name, "sleep 30")


class BuildStage(Stage):
  def __init__(self, commit_id, build_from):
    Stage.__init__(self, commit_id)
    self.build_from = build_from

  def disks(self, driver):
    return [
      # Figure out the src for this commit
      Disk(
        driver=driver,
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=SnapshotName(self.commit_id, "src"),
        mode="ro",
      ),

      # Create the disk we'll use to generate the snapshot onto.
      Disk(
        driver=driver,
        content="out",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=self.build_from,
        save_snapshot=True,
      ),
    ]

  def command(self):
    RunCommandOnInstance(self.instance_name, "sleep 150")



def get_commits_fake():
    return list(reversed(list(c.strip()[:12] for c in file("queue/our-commits.txt", "r").readlines())))


if __name__ == "__main__":
  commits = get_commits_fake()

  latest_sync_snapshot = SnapshotName(commits[0], "src")
  latest_build_snapshot = SnapshotName(commits[0], "out")
  assert SnapshotReady(DRIVER, latest_sync_snapshot), "%s doesn't exist" % latest_sync_snapshot
  assert SnapshotReady(DRIVER, latest_build_snapshot), "%s doesn't exist" % latest_build_snapshot

  stages = []
  for c in commits[1:]:
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

  for s in stages:
    print s, s.can_run(), s.done()

  print "---"
  print "---"

  raw_input("Run things? [y]")

  while stages:
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

    time.sleep(1)
