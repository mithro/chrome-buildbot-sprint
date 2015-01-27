#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:


from objects import *

class Tasklet(object):
  def __repr__(self):
    return '%s(%s%s)' % (self.__class__.__name__, self.tid, self.__repr_extra__())

  def __repr_extra__(self):
    return ''

  def __init__(self, tid):
    self.tid = tid

  def is_startable(self):
    raise NotImplementedError("%s.is_startable()" % self.__class__)

  def is_running(self):
    raise NotImplementedError("%s.is_running()" % self.__class__)

  def is_finished(self):
    raise NotImplementedError("%s.is_finished()" % self.__class__)

  def run(self, driver):
    raise NotImplementedError("%s.run()" % self.__class__)


class CreateXFromY(Tasklet):
  def __repr_extra__(self):
    return ' src=%s dst=%s' % (self.src, self.dst)

  def __init__(self, tid, src, dst):
    Tasklet.__init__(self, tid)
    self.src = src
    self.dst = dst

  def is_startable(self):
    return self.src.exists() and self.src.ready()

  def is_running(self):
    return self.dst.exists() and not self.is_finished()

  def is_finished(self):
    return self.dst.ready()

  def run(self, driver):
    assert self.src.exists()
    assert not self.dst.exists()
    self.dst.create(driver, self.src.name)


class CreateDiskFromSnapshot(CreateXFromY):
  def __init__(self, tid, source_snapshot, destination_disk):
    assert isinstance(source_snapshot, Snapshot)
    assert isinstance(destination_disk, Disk)
    CreateXFromY.__init__(self, tid, src=source_snapshot, dst=destination_disk)


class CreateSnapshotFromDisk(CreateXFromY):
  def __init__(self, tid, source_disk, destination_snapshot):
    assert isinstance(source_disk, Disk)
    assert isinstance(destination_snapshot, Snapshot)
    CreateXFromY.__init__(self, tid, src=source_disk, dst=destination_snapshot)


class CreateInstance(Tasklet):
  def __init__(self, tid, instance, required_snapshots):
    Tasklet.__init__(self, tid)
    self.instance = instance
    self.required_snapshots = required_snapshots

  def is_startable(self):
    for snapshot in self.required_snapshots:
      if not snapshot.ready():
        return False
    return True

  def is_running(self):
    return self.instance.exists() and not self.is_finished()

  def is_finished(self):
    return self.instance.ready()

  def run(self, driver):
    self.instance.create(driver)


class AttachDiskToInstance(Tasklet):
  def __init__(self, tid, instance, disk, mode):
    Tasklet.__init__(self, tid)
    self.instance = instance
    self.disk = disk
    self.mode = mode

  def is_startable(self):
    if not self.instance.exists() or not self.instance.ready():
      return False

    if not self.disk.exists() and self.disk.ready():
      return False

    return True

  def is_running(self):
    return False

  def is_finished(self):
    return self.instance.attached(self.disk)

  def run(self, driver):
    assert self.instance.exists()
    assert self.instance.ready()
    assert self.disk.exists()
    assert self.disk.ready()
    self.instance.attach(driver, self.disk, self.mode)


class DetachDiskFromInstance(AttachDiskToInstance):

  def __init__(self, tid, instance, disk):
    AttachDiskToInstance.__init__(self, tid, instance, disk, None)

  def is_finished(self):
    return not self.instance.attached(self.disk)

  # ----------------------------------------

  def run(self, driver):
    self.instance.detach(driver, self.disk)

      

class MetadataTasklet(Tasklet):
  METADATA_KEY=None
  METADATA_RESULT=None

  def __init__(self, tid, instance):
    Tasklet.__init__(self, tid)
    self.instance = instance

  def _metadata_values(self):
    raise NotImplementedError("%s._metadata_values()" % self.__class__)

  def is_running(self):
    metadata = self.instance.metadata
    if self.METADATA_KEY not in metadata:
      return False

    for data in self._metadata_values():
      if data not in metadata[self.METADATA_KEY]:
        return False

    return not self.is_finished()

  def is_finished(self):
    metadata = self.instance.metadata
    if self.METADATA_RESULT not in metadata:
      return False

    for data in self._metadata_values():
      if data not in metadata[self.METADATA_RESULT]:
        return False

    return True

  @classmethod
  def handle_callback(cls, driver, instance, success, old_value, new_value):
    if success is not True:
      return False
    if new_value is None:
      return False

    metadata = instance.metadata
    if cls.METADATA_RESULT not in metadata:
      metadata[cls.METADATA_RESULT] = []

    if new_value in metadata[cls.METADATA_RESULT]:
      return False

    metadata[cls.METADATA_RESULT].append(new_value)
    instance.set_metadata(driver, {cls.METADATA_RESULT: metadata[cls.METADATA_RESULT]})
    return True

  # ----------------------------------------

  def run(self, driver):
    metadata = self.instance.metadata
    if self.METADATA_KEY not in metadata:
      metadata[self.METADATA_KEY] = []

    for data in self._metadata_values():
      if data not in metadata[self.METADATA_KEY]:
        metadata[self.METADATA_KEY].append(data)

    self.instance.set_metadata(driver, {self.METADATA_KEY: metadata[self.METADATA_KEY]})
    


class MountDisksInInstance(MetadataTasklet):
  METADATA_KEY='mount'
  METADATA_RESULT='mount-result'
  HANDLER='HandlerMount'

  def __init__(self, tid, instance, disks_and_mnts):
    MetadataTasklet.__init__(self, tid, instance)
    assert isinstance(disks_and_mnts, (list, tuple))
    self.disks_and_mnts = disks_and_mnts

  def _metadata_values(self):
    data = [] 
    for disk, mnt in self.disks_and_mnts:
      data.append({
        'mount-point': mnt,
        'disk-id': disk.name,
        'user': 'ubuntu',
        'tid': self.tid,
      })
    return data

  def is_startable(self):
    for d, mnt in self.disks_and_mnts:
      if not self.instance.attached(d):
        return False
    return True


class UnmountDisksInInstance(MountDisksInInstance):
  METADATA_KEY='umount'
  METADATA_RESULT='umount-result'
  HANDLER='HandlerUnmount'



class RunCommandOnInstance(MetadataTasklet):
  METADATA_KEY='long-commands'
  METADATA_RESULT='long-commands-result'
  HANDLER='HandlerLongCommand'

  def __init__(self, tid, instance, command):
    MetadataTasklet.__init__(self, tid, instance)
    self.command = command
    
  def _metadata_values(self):
    return [{'cmd': self.command, 'user': 'ubuntu'}]

  def is_startable(self):
    return self.instance.ready()


class WaitOnOtherTasks(Tasklet):
  def __repr_extra__(self):
    return " %s %s" % (self.task_to_run, self.tasks_to_wait_for)

  def __init__(self, task_to_run, tasks_to_wait_for):
    Tasklet.__init__(self, task_to_run.tid)
    self.task_to_run = task_to_run
    self.tasks_to_wait_for = tasks_to_wait_for

  def is_startable(self):
    if not self.task_to_run.is_startable():
      return False

    for task in self.tasks_to_wait_for:
      if not task.is_finished():
        return False

    return True

  def is_running(self):
    return self.task_to_run.is_running()

  def is_finished(self):
    if not self.task_to_run.is_finished():
      return False

    for task in self.tasks_to_wait_for:
      if not task.is_finished():
        return False

    return True

  def run(self, driver):
    return self.task_to_run.run(driver)

class CancelledByOtherTask(Tasklet):
  def __init__(self, task_to_run, task_indicating_finished):
    Tasklet.__init__(self, task_to_run.tid)
    self.task_to_run = task_to_run
    self.task_indicating_finished = task_indicating_finished

  def is_startable(self):
    return self.task_to_run.is_startable()

  def is_running(self):
    return self.task_to_run.is_running()

  def is_finished(self):
    return self.task_to_run.is_finished() or self.task_indicating_finished.is_finished()

  def run(self, driver):
    return self.task_to_run.run(driver)

