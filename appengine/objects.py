#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:


class GCEObject(object):
  def __init__(self, name):
    self.name = name

  def _gce_obj(self, driver):
    raise NotImplementedError()

  def _gce_destroy_func(self, driver):
    raise NotImplementedError()

  def _status(self, driver):
    try:
      self._gce_obj(driver).status['status']
    except ResourceNotFoundError:
      return "IMAGINARY"

  def _create_time(self, driver):
    return parseTime(self._gce_obj(driver).extra['creationTimestamp'])

  def __eq__(self, other):
    return type(self) == type(other) and self.name == other.name

  def exists(self, driver):
    try:
      return True
    except ResourceNotFoundError:
      return False

  def ready(self, driver):
    try:
      if self._status(driver) != "READY":
        return False
      return True
    except ResourceNotFoundError:
      return False

  def destroy(self, driver):
    assert self.exists(driver)
    assert self.ready(driver)
    TimerLog.log(self, "DESTROY")
    self._gce_destory_func(driver)(self._gce_obj(driver))



class Disk(GCEObject):
  def _gce_obj(self, driver):
    return driver.ex_get_volume(self.name)

  def _gce_destory_func(self, driver):
    return driver.destroy_volume

  def create(self, driver, from_snapshot):
    TimerLog.log(self, "CREATE")
    driver.create_volume(size=None, name=self.name, snapshot=from_snapshot, ex_disk_type='pd-ssd')




class Snapshot(GCEObject):
  def _gce_obj(self, driver):
    return driver.ex_get_snapshot(self.name)

  def _gce_destory_func(self, driver):
    return driver.destroy_volume_snapshot

  # For some reason snapshot status is only available via .status rather than
  # .extra['status']!?
  def _status(self, driver):
    try:
      return self._gce_obj(driver).status
    except ResourceNotFoundError:
      return "IMAGINARY"

  def create(self, driver, from_disk):
    TimeLog.log(self, "CREATE")
    driver.create_volume_snapshot(driver.ex_get_volume(from_disk), self.name)



class Instance(GCEObject):
  def _gce_obj(self, driver):
    return driver.ex_get_node(self.name)

  def _gce_destory_func(self, driver):
    return driver.destroy_node

  MACHINE_TYPE = 'n1-standard-2'
  BOOT_IMAGE = 'boot-image-wip-2'
  STARTUP_SCRIPT = 'metadata_watcher.py'
  TAGS=('http-server',)
  def create(self, driver):
    TimerLog.log(self, "CREATE")
    
    node = driver.deploy_node(
      self.name,
      size=self.MACHINE_TYPE,
      image=self.IMAGE,
      script=self.STARTUP_SCRIPT,
      ex_tags=self.TAGS)

  def public_ips(self, driver):
    try:
      return self._gce_obj(driver).public_ips
    except ResourceNotFoundError:
      return []

  def fetch(self, driver, name=""):
    if name:
      name = '/%s' % name

    try:
      return urllib2.urlopen(
          "http://%s/tmp%s" % (
              self.public_ips(driver)[0], name)).read()
    except (urllib2.HTTPError, urllib2.URLError) as e:
      return None

  def ready(self, driver):
    if not GCEObject.ready(driver):
      return False

    if not self.fetch(driver):
      return False

    return True

  def attach(self, driver, disk, mode):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists(driver)
    assert disk.ready(driver)

    TimerLog.log(self, "ATTACH", disk, mode)

    driver.attach_volume(
      node=self._gce_obj(driver),
      volume=disk._gce_obj(driver),
      device=disk.name,
      ex_mode=mode)

  def attached(self, driver, disk):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists(driver)
    assert disk.ready(driver)
    return disk in self.disks(driver)

  def disks(self, driver):
    disks = []
    for d in self._gce_obj(driver).extra['disks']:
      if d['kind'] != 'compute#attachedDisk':
        continue

      disk = Disk(d['deviceName'])
      assert disk.exists(driver)
      assert disk.ready(driver)
      disks.append(disk)
    return disks 

  def detach(self, driver, disk):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists(driver)
    assert disk.ready(driver)
    assert disk in self.disks(driver)

    TimeLog.log(self, "DETACH", disk)
    driver.detach_volume(
      volume=disk._gce_obj(driver),
      ex_node=self._gce_obj(driver))

  def get_metadata(self, driver):
    metadata = {}
    for d in self._gce_obj(driver).extra['metadata']['items']:
      v = d['value']
      if v.startswith('{') or v.startswith('[') or v.startswith('"'):
        try:
          v = simplejson.loads(v)
        except:
          pass
      metadata[d['key']] = d['value']
    return metadata

  def set_metadata(self, driver, data=None, **kw):
    metadata = self.metadata(driver)
    if data:
      metadata.update(kw)
    metadata.update(kw)
    for key in metadata.keys():
      v = metadata[key]
      if isinstance(v, (int, long, float, str, unicode)):
        continue
      elif isinstance(metadata[key], (list, dict)):
        metadata[key] = simplejson.dumps(metadata[key])
      else:
        raise TypeError("Can't set metadata key %s to %r" % (key, v))
    driver.ex_set_node_metadata(self._gce_obj(driver), metadata)

