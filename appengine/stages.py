#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:



class SyncStage(object):

  def tasklets(self):
    #prev = '-'.
    task_id = '-'.join([NoDash(getpass.getuser()), NoDash(commit), NoDash(BUILD_PLATFORM), self.__class__.__name__])

    previous_snap_src = Snapshot("%s-snapshot-src" % task_id)

    instance = Instance("%s-instance" % task_id)
    disk_src = Disk("%s-disk-src" % task_id)
    snap_src = Snapshot("%s-snapshot-src" % task_id)

    tasks = []
    tasks.append(CreateInstance(task_id, instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(task_id, previous_snap_src, disk_src))
    tasks.append(AttachDiskToInstances(task_id, instance, disk_src))
    tasks.append(MountDisksInInstance(task_id, instance, [(disk_src, "/mnt")]))

    run_task = RunCommandOnInstance(task_id, instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time gclient sync -r %s
""")
    tasks.append(run_task)

    umount_task = UmountDisksInInstance(task_id, instance, src_disk)
    tasks.append(WaitOnOtherTasks(task_id, umount_task, [run_task]))

    detach_task = DetachDisksFromInstance(task_id, instance, disk)
    tasks.append(detach_task)

    snapshot_task = CreateSnapshotFromDisk(task_id, disk_src, snap_src)
    tasks.append(WaitOnOtherTasks(task_id, snapshot_task, [detatch_task]))

    return tasks


class BuildStage(object):
  def tasklets(self):
    task_id = '-'.join([NoDash(getpass.getuser()), NoDash(commit), NoDash(BUILD_PLATFORM), self.__class__.__name__])

    current_snap_src = Snapshot("%s-snapshot-src" % task_id)
    previous_snap_out = Snapshot("%s-snapshot-out" % task_id)

    instance = Instance("%s-instance" % task_id)
    disk_src = Disk("%s-disk-src" % task_id)
    disk_out = Disk("%s-disk-out" % task_id)
    snap_out = Snapshot("%s-snapshot-out" % task_id)

    tasks = []
    tasks.append(CreateInstance(task_id, instance, required_snapshots=[previous_snap_src]))
    tasks.append(CreateDiskFromSnapshot(task_id, current_snap_src, disk_src))
    tasks.append(CreateDiskFromSnapshot(task_id, previous_snap_out, disk_out))
    tasks.append(AttachDiskToInstances(task_id, instance, disk_src))
    tasks.append(AttachDiskToInstances(task_id, instance, disk_out))
    tasks.append(MountDisksInInstance(task_id, instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")]))

    run_task = RunCommandOnInstance(task_id, instance, """\
export PATH=$PATH:/mnt/chromium/depot_tools;
cd /mnt/chromium/src;
time build/gyp_chromium;
time ninja -C out/Debug;
""")
    tasks.append(run_task)

    umount_task = UnountDisksInInstance(task_id, instance, [(disk_src, "/mnt/chromium"), (disk_out, "/mnt/chromium/src/out")])
    tasks.append(WaitOnOtherTasks(task_id, umount_task, [run_task]))

    detach_src_task = DetachDiskFromInstances(task_id, instance, disk_src)
    detach_out_task = DetachDiskFromInstances(task_id, instance, disk_out)
    tasks.append(WaitOnOtherTasks(task_id, detach_src_task, [umount_task]))
    tasks.append(WaitOnOtherTasks(task_id, detach_out_Task, [umount_task]))

    snapshot_out_task = CreateSnapshotFromDisk(task_id, disk_out, snap_out)
    tasks.append(WaitOnOtherTasks(task_id, snapshot_task, [detach_out_task]))

    return task


if __name__ == "__main__":
  previous_commit = "commit0"
  current_commit = "commit1"
  

  print SyncStage(previous_commit, current_commit).tasklists()
  print BuildStage(previous_commit, current_commit).tasklists()


# Tasks
# create instances
#  * snapshot exists
# create disks from snapshot
#  * snapshot exists
# attach disks to instance
#  * disk exists
#  * instance exists
# mount disks on instance
#  * disks attached
# run command
#  * disks mounted
# unmount disks
#  * command run
# create snapshot from disks
#  * disks unmount
# delete disks
#  * snapshots ready
# delete instance
#  * disks unmounted



for t in tasklets:
  # Task has already finished
  done_for = time.time() - t.done()
  if done_for > t.cleanup_period:
    t.cleanup()
    continue
  elif done_for > 0:
    continue

  # Task is ready to start
  ready_for = time.time() - t.ready()
  if ready_for < 0:
    continue

  # Task is running
  running_for = time.time() - t.running()
  if running_for < 0:
    t.run()
    continue

  if running_for > t.timeout:
    t.abort()
    continue

   



































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
    if args:
      s = s % args
    print reltime(), "%s(%s): instance(%s)" % (self.stage, self.commit_id, self.name), s

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
    node = self.driver.deploy_node(self.name, size=machine_type, image='boot-image-wip-2', script=STARTUP_SCRIPT, ex_tags=['http-server'])
    self.log('Public IPs: %s', ["http://%s/tmp" % i for i in node.public_ips])
    for disk in disks:
      self.driver.attach_volume(node, self.driver.ex_get_volume(disk.name), disk.name, disk.mode)
    self.disks = disks
    while True:
      try:
        urllib2.urlopen("http://%s/tmp" % (node.public_ips[0])).read()
        break
      except (urllib2.HTTPError, urllib2.URLError) as e:
        time.sleep(1)
    self.timer.stop("launch")

  def run(self, command):
    tmpfile = md5.md5(command).hexdigest()
    self.log("running %r", command)
    self.timer.start("run_command")
    node = self.driver.ex_get_node(self.name)
    self.update_metadata({'long-commands': simplejson.dumps([
          {'cmd': command, 
           'user':'ubuntu', 
           'output-file':'/tmp/%s' % tmpfile},
        ])}, node)
    while True:
      try:
        result = simplejson.loads(
            urllib2.urlopen("http://%s/tmp/%s" % (node.public_ips[0], tmpfile)).read()
            )
        self.log('Last 50 lines of output\n%s\n%s\n%s\n', '-'*80, '\n'.join(result['output'].split('\n')[-50:]), '-'*80)
        self.log('command %s was successful? %s', command, result['success'])
        break
      except (urllib2.HTTPError, urllib2.URLError) as e:
        time.sleep(1)
      except Exception, e:
        self.log(e)
        time.sleep(1)

    self.timer.stop("run_command")

  def mount_disks(self):
    # Mount the disks into the VM
    self.timer.start("mounting_disks")
    disk_mnt = []
    for disk in self.disks:
      disk_mnt.append({'disk-id': disk.name, 'mount-point': disk.mnt, 'user': 'ubuntu'})
    self.update_metadata({'mount': simplejson.dumps(disk_mnt)})
    self.timer.stop("mounting_disks")

  def shutdown(self):
    self.timer.start("shutdown")
    self.update_metadata({'shutdown': simplejson.dumps(time.time())})
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
    if args:
      s = s % args
    print reltime(), "%s(%s): disk(%s)" % (self.stage, self.commit_id, self.name), s

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
      "src": "/mnt/chromium",
      "out": "/mnt/chromium/src/out",
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
      while self.driver.ex_get_volume(self.name).extra['status'] != "READY":
        time.sleep(1)
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
    if args:
      s = s % args
    print reltime(), repr(self), s

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

    self.run_complete = False

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
      'cd /mnt/chromium/src',
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
      'cd /mnt/chromium/src',
      'time build/gyp_chromium',
      'time ninja -C out/Debug',
    ]))

class TestStage(Stage):
  def __init__(self, commit_id, test_binaries, total_shards=1, shard_index=0):
    Stage.__init__(self, commit_id)
    self.test_binaries = test_binaries
    self.total_shards = total_shards
    self.shard_index = shard_index

  def disks(self, driver):
    return [
      Disk(
        driver=driver,
        content="src",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=SnapshotName(self.commit_id, "src"),
        mode="READ_ONLY",
      ),
      Disk(
        driver=driver,
        content="out",
        commit_id=self.commit_id,
        stage=self.name(),
        from_snapshot=SnapshotName(self.commit_id, "out"),
      ),
    ]

  def command(self, instance):
    shard_variables = ('GTEST_TOTAL_SHARDS=%(total)d GTEST_SHARD_INDEX=%(index)d '
                       % {'total': self.total_shards, 'index': self.shard_index})
    xvfb_command = 'xvfb-run --server-args=\'-screen 0, 1024x768x24\' '
    command = ' && '.join(
      [
        'sudo apt-get install xvfb -y',
        'chromium/src/build/update-linux-sandbox.sh',
        'export CHROME_DEVEL_SANDBOX=/usr/local/sbin/chrome-devel-sandbox',
      ] +
      [shard_variables + xvfb_command +
       ('chromium/src/out/Debug/%(test_binary)s --gtest_output="xml:%(test_binary)s.xml"'
        % {'test_binary': b}) for b in self.test_binaries])
    self.log('Test command: ' + command)
    instance.run(command)

    for test_binary in self.test_binaries:
      cat_command = 'cat %(test_binary)s.xml' % {'test_binary': test_binary}
      result = instance.run(cat_command)
      # Sometimes the output is not piped back correctly. Try it a few times.
      if not result:
        result = instance.run(cat_command)
      if not result:
        result = instance.run(cat_command)
      open(InstanceName(self.name(), self.commit_id) + '-' + test_binary, 'w').write(result)

def get_commits_fake():
    return list(reversed(list(c.strip()[:16] for c in file("queue/our-commits.txt", "r").readlines())))


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
    # This needs to be sharded out.
    # stages.append(TestStage(c, [TEST_BINARIES]))
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

  # raw_input("Run things? [Y/y]")

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
