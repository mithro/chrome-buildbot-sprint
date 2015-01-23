#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import time

from google.appengine.api import memcache

from helpers import *
from libcloud_gae import ResourceNotFoundError


def parse_time(timestamp_str):
  dt = dateutil.parser.parse(timestamp_str)
  return calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond


class GCEObject(dict):
  def __init__(self, name):
    dict.__init__(self)
    self.name = name

  # All attributes are dict entries
  def __setattr__(self, key, value):
    self[key] = value

  def __getattr__(self, key):
    return self[key]

  # For pickle
  def __setstate__(self, state):
    self.__dict__ = state

  def __getstate__(self):
    return self.__dict__

  def _gce_obj(self, driver):
    raise NotImplementedError()

  def _gce_destroy_func(self, driver):
    raise NotImplementedError()

  def _status(self, gce_obj):
    try:
      return gce_obj.extra['status']
    except ResourceNotFoundError:
      return "IMAGINARY"

  def _create_time(self, gce_obj):
    try:
      return parse_time(gce_obj.extra['creationTimestamp'])
    except ResourceNotFoundError:
      return inf

  def _cache_key(self):
    return type(self).__name__.lower() + ':' + self.name

  def __eq__(self, other):
    return type(self) == type(other) and self.name == other.name

  def update_from_gce(self, gce_obj):
    self.name = gce_obj.name
    self.create_time = self._create_time(gce_obj)
    self.status = self._status(gce_obj)
    memcache.set(self._cache_key(), self, time=120)

  def load(self, name, driver):
    cached = memcache.get(self._cache_key())
    if cached:
      self.update(cached)
    else:
      self.update_from_gce(driver.ex_get_volume(name))

  def exists(self):
    return self.create_time != inf

  def ready(self):
    return self.status == "READY"

  def destroy(self, driver):
    assert self.exists()
    assert self.ready()
    TimerLog.log(self, "DESTROY")
    self._gce_destory_func(driver)(self._gce_obj(driver))


class Disk(GCEObject):

  def _gce_obj(self, driver):
    return driver.ex_get_volume(self.name)

  def _gce_destory_func(self, driver):
    return driver.destroy_volume

  def create(self, driver, from_snapshot):
    TimerLog.log(self, "CREATE")
    self.update_from_gce(
        driver.create_volume(size=None, name=self.name, snapshot=from_snapshot, ex_disk_type='pd-ssd'))


class Snapshot(GCEObject):
  def _gce_obj(self, driver):
    return driver.ex_get_snapshot(self.name)

  def _gce_destory_func(self, driver):
    return driver.destroy_volume_snapshot

  # For some reason snapshot status is only available via .status rather than
  # .extra['status']!?
  def _status(self, gce_obj):
    try:
      return gce_obj.status
    except ResourceNotFoundError:
      return "IMAGINARY"

  def create(self, driver, from_disk):
    TimeLog.log(self, "CREATE")
    self.update_from_gce(
       driver.create_volume_snapshot(driver.ex_get_volume(from_disk), self.name))



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
    metadata = self.get_metadata(driver)
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

