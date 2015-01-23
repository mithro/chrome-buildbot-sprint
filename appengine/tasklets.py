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
    raise NotImplementedError()

  def is_running(self):
    raise NotImplementedError()

  def is_finished(self):
    raise NotImplementedError()

  def run(self, driver):
    raise NotImplementedError()


class CreateXFromY(Tasklet):
  def __repr_extra__(self):
    return ' src=%s dst=%s' % (self.src, self.dst)

  def __init__(self, tid, src, dst):
    Tasklet.__init__(self, tid)
    self.src = src
    self.dst = dst

  def is_startable(self):
    return self.src.exists()

  def is_running(self):
    return self.dst.exists()

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
    return self.instance.exists()

  def is_finished(self):
    return self.instance.ready()

  def run(self, driver):
    self.instance.create(driver)


class AttachDiskToInstance(Tasklet):
  def __init__(self, tid, instance, disk):
    Tasklet.__init__(self, tid)
    self.instance = instance
    self.disk = disk

  def is_startable(self):
    if not self.instance.exists():
      return False

    if not self.disk.exists():
      return False

    return True

  def is_running(self):
    return True

  def is_finished(self):
    return self.instance.attached(self.disk)

  def run(self, driver):
    assert self.instance.exists(driver)
    assert self.disk.exists(driver)
    self.instance.attach(driver, disk)


class DetachDiskFromInstance(AttachDiskToInstance):
  def is_startable(self):
    if not self.instance.exists():
      return False

    if not self.disks.exists():
      return False

    return True

  def is_running(self):
    return True

  def is_finished(self):
    return not self.instance.attached(self.disk)

  # ----------------------------------------

  def run(self, driver):
    self.instance.detach(driver, disk)

      

class MetadataTasklet(Tasklet):
  METADATA_KEY=None
  METADATA_RESULT=None

  def __init__(self, tid, instance):
    Tasklet.__init__(self, tid)
    self.instance = instance

  def _metadata_values(self):
    raise NotImplementedError()

  def is_running(self):
    metadata = self.instance.metadata
    if self.METADATA_KEY not in metadata:
      return False

    for data in self._metadata_values():
      if data not in metadata[self.METADATA_KEY]:
        return False
    return True

  def is_finished(self):
    metadata = self.instance.metadata
    if self.METADATA_RESULT not in metadata:
      return False
    return True

  # ----------------------------------------

  def run(self, driver):
    metadata = self.instance.metadata
    if self.METADATA_KEY not in metadata:
      metadata[self.METADATA_KEY] = []

    for data in self._metadata_values():
      if data not in metadata[self.METADATA_KEY]:
        metadata[self.METADATA_KEY].append(data)

    self.instance.set_metadata(driver, mount=metadata[self.METADATA_KEY])
    


class MountDisksInInstance(MetadataTasklet):
  METADATA_KEY='mount'

  def __init__(self, tid, instance, disks_and_mnts):
    MetadataTasklet.__init__(self, tid, instance)
    assert isinstance(disks_and_mnts, (list, tuple))
    self.disks_and_mnts = disks_and_mnts

  def _metadata_values(self):
    data = [] 
    for disk, mnt in self.disks:
      data.append({
        'mount-point': mnt,
        'disk-id': disk.name,
        'user': 'ubuntu',
      })
    return data

  def is_startable(self):
    for d, mnt in self.disks_and_mnts:
      if not AttachDiskToInstance(None, self.instance, d).is_finished():
        return False
    return True

  def is_finished(self):
    return self.instance.fetch("mount") is not None


class UnmountDisksInInstance(MountDisksInInstance):
  METADATA_KEY='umount'



class RunCommandOnInstance(MetadataTasklet):
  METADATA_KEY='long-commands'

  def __init__(self, tid, instance, command):
    MetadataTasklet.__init__(self, tid, instance)
    self.command = command
    
  def _required_metadata(self):
    return [self.command]

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
    return self.task_to_run.is_finished() and self.is_startable()

  # Map everything else onto the task which should run
  def __getattr__(self, key):
    return getattr(self, self.task_to_run, key)

  

