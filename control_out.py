#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import sys
sys.path.append("libcloud")

import getpass
import subprocess

MACHINE_SIZE = 'n1-standard-1'
BUILD_PLATFORM = "linux"
SHARED_COMMANDS = {
  'depot_tools_path': 'export PATH=~/chromium/depot_tools:"$PATH"',
}

import time
def reltime(starttime=time.time()):
  return "[%.1fs]" % (time.time() - starttime)


def NoDash(string):
  return string.replace('-', '_')


# Basic wrapper around the gcloud commands
# --------------------------------------------------------

from libcloud.common.google import ResourceNotFoundError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.ssh import ParamikoSSHClient as SSHClient

# HACK: Extend the request timeout to 10 minutes up from 3 minutes.
from libcloud.common.google import GoogleBaseConnection
GoogleBaseConnection.timeout = 600

PROJECT_ID = 'delta-trees-830'
REGION = 'us-central1'
ZONE = 'us-central1-a'

SERVICE_ACCOUNT_EMAIL = '621016184110-tpkj4skaep6c8ccgolhoheepffasa9kq@developer.gserviceaccount.com'
SERVICE_ACCOUNT_KEY_PATH = 'chrome-buildbot-sprint-c514ee5826d1.pem'
SCOPES = ['https://www.googleapis.com/auth/compute']

SSH_KEY_PATH = 'gce_bot_rsa'
STARTUP_SCRIPT = 'startup_script.sh'

ComputeEngine = get_driver(Provider.GCE)
def new_driver():
  print reltime(), "creating new driver", threading.currentThread()
  return ComputeEngine(SERVICE_ACCOUNT_EMAIL,
                       SERVICE_ACCOUNT_KEY_PATH,
                       datacenter=ZONE,
                       project=PROJECT_ID,
                       auth_type='SA',
                       scopes=SCOPES)

# Snapshots
def SnapshotReady(driver, snapshot_name):
  try:
    ss = driver.ex_get_snapshot(snapshot_name)
    return ss.status == 'READY'
  except ResourceNotFoundError:
    return False

def ImageName():
  return 'boot-image-wip'

# Naming
def DiskName(stage, commit, content):
  return '-'.join([NoDash('acmerge'), 'disk', NoDash(BUILD_PLATFORM), NoDash(commit), stage, content])

def InstanceName(stage, commit):
  return '-'.join([NoDash('acmerge'), 'instance', NoDash(BUILD_PLATFORM), NoDash(commit), stage])

def SnapshotName(commit, content):
  return '-'.join([NoDash('acmerge'), 'snapshot', NoDash(BUILD_PLATFORM), NoDash(commit), content])


# --------------------------------------------------------

import cStringIO as StringIO
import collections
import threading
import traceback

class Timer(object):
  def __init__(self, logger=None):
    self.start_times = {}
    self.named_durations = collections.OrderedDict()
    self.logger = logger

  def start(self, name):
    self.start_times[name] = time.time()
    if self.logger:
      self.logger.log('%s START', name)

  def stop(self, name):
    duration = time.time() - self.start_times[name]
    self.named_durations.setdefault(name, []).append(duration)
    if self.logger:
      self.logger.log('%s COMPLETE (%.1fs)', name, duration)

  def update(self, timer):
    for name, durations in timer.named_durations.items():
      self.named_durations.setdefault(name, []).extend(durations)

  def sum(self):
    for name, durations in self.named_durations.items():
      self.named_durations[name] = [sum(durations)]

  def __str__(self):
    s = '{\n'
    for name, durations in self.named_durations.items():
      s += '  %s: %s\n' % (name, ', '.join('%.1fs' % duration for duration in durations))
    s += '}'
    return s

class Instance(object):
  def log(self, s, *args):
    print reltime(), "%s(%s): instance(%s)" % (self.stage, self.commit_id, self.name), s % args

  def __init__(self, driver, stage, commit_id):
    self.driver = driver
    self.stage = stage
    self.commit_id = commit_id
    self.disks = []
    self.timer = Timer(logger=self)

  @property
  def name(self):
    return InstanceName(self.stage, self.commit_id)

  def exists(self):
    try:
      self.driver.ex_get_node(self.name)
      return True
    except ResourceNotFoundError:
      return False

  def launch(self, machine_type, disks):
    self.timer.start("launch")
    self.node = self.driver.deploy_node(self.name, size=machine_type, image=ImageName(), script=STARTUP_SCRIPT)
    for disk in disks:
      self.driver.attach_volume(self.node, self.driver.ex_get_volume(disk.name), disk.name, disk.mode)
    self.disks = disks
    self.timer.stop("launch")

  def run(self, command):
    self.log("running %r", command)
    self.timer.start("run_command")
    node = self.driver.ex_get_node(self.name)
    ssh = SSHClient(node.public_ips[0], username='ubuntu', key=SSH_KEY_PATH)
    ssh.connect()
    stdout, stderr, returncode = ssh.run(command)
    ssh.close()
    if returncode != 0:
      raise subprocess.CalledProcessError(returncode, command, stdout + stderr)
    self.timer.stop("run_command")

  def wait_until_ready(self):
    self.timer.start("wait_for_ssh")
    while True:
      try:
        self.run("true")
        break
      except Exception, e:
        self.log("waiting %s", e)
        time.sleep(0.5)
    self.timer.stop("wait_for_ssh")

  def mount_disks(self):
    # Mount the disks into the VM
    self.timer.start("mounting_disks")
    cmd = ""
    for disk in self.disks:
      cmd += """\
mkdir -p %(mnt)s; \
sudo mount /dev/disk/by-id/google-%(name)s %(mnt)s; \
""" % {"name": disk.name, "mnt": disk.mnt}
    self.run(cmd)
    self.timer.stop("mounting_disks")

  def shutdown(self):
    self.timer.start("shutdown")
    self.run("sudo shutdown -h now")
    try:
      while self.driver.ex_get_node(self.name).state == 'RUNNING':
        time.sleep(1)
    except ResourceNotFoundError:
      pass
    self.timer.stop("shutdown")

  def delete(self):
    self.timer.start("delete")
    self.driver.destroy_node(self.driver.ex_get_node(self.name))
    self.timer.stop("delete")


class Disk(object):
  def log(self, s, *args):
    print reltime(), "%s(%s): disk(%s)" % (self.stage, self.commit_id, self.name), s % args

  def __init__(self, driver, content, commit_id, stage, from_snapshot, mode="READ_WRITE", save_snapshot=False):
    self.driver = driver

    self.content = content
    self.commit_id = commit_id

    self.stage = stage
    self.from_snapshot = from_snapshot
    self.mode = mode
    self.save_snapshot = save_snapshot
    self.timer = Timer(logger=self)

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
    try:
      self.driver.ex_get_volume(self.name)
      return True
    except ResourceNotFoundError:
      return False

  def can_create(self):
    return SnapshotReady(self.driver, self.from_snapshot)

  def create(self):
    self.timer.start("create")
    assert not self.exists()
    self.driver.create_volume(size=None, name=self.name, snapshot=self.from_snapshot, ex_disk_type='pd-ssd')
    self.timer.stop("create")

  def cleanup(self, clear_snapshot=False):
    self.timer.start("clean_up")
    if self.exists():
      self.timer.start("clean_up_disk")
      self.driver.destroy_volume(self.driver.ex_get_volume(self.name))
      self.timer.stop("clean_up_disk")
      self.log("deleted disk %s", self.name)

    if clear_snapshot and self.save_snapshot:
      if SnapshotReady(self.driver, self.snapshot_name):
        self.timer.start("clean_up_snapshot")
        self.driver.destroy_volume_snapshot(self.driver.ex_get_snapshot(self.snapshot_name))
        self.timer.stop("clean_up_snapshot")
        self.log("deleted snapshot %s", self.snapshot_name)
    self.timer.stop("clean_up")

  def save(self):
    if self.save_snapshot:
      self.timer.start("save_snapshot")
      volume = self.driver.ex_get_volume(self.name)
      self.driver.create_volume_snapshot(volume, self.snapshot_name)
      self.timer.stop("save_snapshot")
      self.log("created snapshot %s", self.snapshot_name)

  def saved(self):
    if self.save_snapshot:
      return SnapshotReady(self.driver, self.snapshot_name)
    return True


class Stage(threading.Thread):
  def log(self, s, *args):
    print reltime(), repr(self), s % args if args else s

  @classmethod
  def name(cls):
    return cls.__name__.lower()[:-len("stage")]

  def __init__(self, commit_id):
    threading.Thread.__init__(self)

    assert self.name() is not Stage.name()
    self.commit_id = commit_id
    self.run_complete = False

    self.timer = Timer(logger=self)
    self.instance_timer = None
    self.disk_timers = None

  def __repr__(self):
    return "%s(%s)" % (self.name(), self.commit_id)

  def can_run(self, driver):
    for disk in self.disks(driver):
      if not disk.can_create():
        return False
    return True

  def done(self, driver):
    for disk in self.disks(driver):
      if not disk.saved():
        return False
    return self.run_complete

  def instance(self, driver):
    return Instance(driver, self.name(), self.commit_id)

  def run(self):
    self.timer.start("run")
    driver = new_driver()

    assert not self.done(driver)

    disks = self.disks(driver)
    instance = self.instance(driver)
    assert not instance.exists()
    try:
      self.timer.start("ready_disks")
      for disk in disks:
        disk.create()
      self.timer.stop("ready_disks")

      self.timer.start("ready_instance")
      instance.launch(self.machine_type, disks)
      instance.wait_until_ready()
      instance.mount_disks()
      self.timer.stop("ready_instance")

      self.timer.start("run_command")
      self.command(instance)
      self.timer.stop("run_command")

      self.timer.start("shutdown_instance")
      instance.shutdown()
      self.timer.stop("shutdown_instance")

      self.timer.start("snapshot_disks")
      for disk in disks:
        disk.save()
      self.timer.stop("snapshot_disks")

    except Exception, e:
      tb = StringIO.StringIO()
      traceback.print_exc(file=tb)
      tb.seek(0)
      self.log("Exception: %s", e)
      self.log(tb.getvalue())
      raise

    self.log("finalizing")

    self.timer.start("delete_instance")
    if instance.exists():
      instance.delete()
    self.timer.stop("delete_instance")

    self.timer.start("clean_up_disks")
    for disk in disks:
      disk.cleanup()
    self.timer.stop("clean_up_disks")

    self.run_complete = True
    self.timer.stop("run")

    self.instance_timer = instance.timer
    self.disk_timers = dict((disk.name, disk.timer) for disk in disks)


class SyncStage(Stage):
  def __init__(self, commit_id, sync_from):
    self.sync_from = sync_from
    Stage.__init__(self, commit_id)

  @property
  def machine_type(self):
    return 'n1-standard-2'

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

  def command(self, instance):
    instance.run(' && '.join([
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

  def disks(self, driver):
    return [
      # Figure out the src for this commit
      Disk(
        driver=driver,
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=SnapshotName(self.commit_id, "src"),
        mode="READ_ONLY",
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

  def command(self, instance):
    instance.run(' && '.join([
      SHARED_COMMANDS['depot_tools_path'],
      'cd chromium/src',
      'time build/gyp_chromium',
      'time ninja -C out/Debug',
    ]))


def get_commits_fake():
    return list(reversed(list(c.strip()[:12] for c in file("queue/our-commits.txt", "r").readlines())))


if __name__ == "__main__":
  driver = new_driver()
  commits = get_commits_fake()[:2]

  latest_sync_snapshot = SnapshotName(commits[0], "src")
  latest_build_snapshot = SnapshotName(commits[0], "out")
  assert SnapshotReady(driver, latest_sync_snapshot), "%s doesn't exist" % latest_sync_snapshot
  assert SnapshotReady(driver, latest_build_snapshot), "%s doesn't exist" % latest_build_snapshot

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
    instance = s.instance(driver)
    if instance.exists():
      instance.delete()

    # Clean up any leftover disks from previous runs.
    for disk in s.disks(driver):
      disk.cleanup(clear_snapshot=True)
  print "---"
  print "---"

  for s in stages:
    print s, s.can_run(driver), s.done(driver)

  print "---"
  print "---"

  raw_input("Run things? [Y/y]")

  all_finished_stages = []
  while stages:
    finished_stages = [s for s in stages if s.done(driver)]
    if finished_stages:
      print reltime(), "Finished", finished_stages
      stages = [s for s in stages if not s in finished_stages]
      all_finished_stages += finished_stages

    running_stages = []
    for stage in stages:
      if stage.can_run(driver) and not stage.is_alive():
        if not stage.done(driver):
          print reltime(), "Starting", stage
          stage.start()

      if stage.is_alive():
        running_stages.append(stage)

    if running_stages:
      print reltime(), "Currently running stages:", running_stages

    time.sleep(10)

  print '---'
  print '---'

  print 'All stages complete'
  aggregate_stage_timer = Timer()
  aggregate_instance_timer = Timer()
  aggregate_disk_timer = Timer()
  for stage in all_finished_stages:
    print stage, 'durations', stage.timer
    aggregate_stage_timer.update(stage.timer)
    print stage, 'instance durations', stage.instance_timer
    aggregate_instance_timer.update(stage.instance_timer)
    for disk_name, disk_timer in stage.disk_timers.items():
      print stage, disk, 'durations', disk_timer
      aggregate_disk_timer.update(disk_timer)
    print
  aggregate_stage_timer.sum()
  aggregate_instance_timer.sum()
  aggregate_disk_timer.sum()
  print 'Total stage durations:', aggregate_stage_timer
  print 'Total instance durations:', aggregate_instance_timer
  print 'Total disk durations:', aggregate_disk_timer
