#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import time
import urllib2

try:
  from google.appengine.api import memcache
except ImportError:
  class FakeMemcache(dict):
    def set(self, key, value, time):
      self[key] = value

    def get(self, key):
      try:
        return self[key]
      except KeyError:
        return None

    def delete(self, key):
      if key in self:
        del self[key]

  memcache = FakeMemcache()

from helpers import *
from libcloud_gae import ResourceNotFoundError


def parse_time(timestamp_str):
  dt = dateutil.parser.parse(timestamp_str)
  return calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond


class GCEObject(dict):
  # All attributes are dict entries
  def __setattr__(self, key, value):
    self[key] = value

  def __getattr__(self, key):
    return self[key]

  # For pickle and memcache
  def __setstate__(self, state):
    self.__dict__ = state

  def __getstate__(self):
    return self.__dict__

  def _cache_key(self):
    return type(self).__name__.lower() + ':' + self.name

  # Functions to get/destroy stuff on gce
  def _gce_obj_get(self, driver):
    raise NotImplementedError()

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    raise NotImplementedError()

  @staticmethod
  def _gce_obj_status(gce_obj):
    return gce_obj.extra['status']

  def update_from_gce(self, gce_obj):
    self.name = gce_obj.name
    self.create_time = parse_time(gce_obj.extra['creationTimestamp'])
    self.status = self._gce_obj_status(gce_obj)

  # ---------------------------------
  _sentinal = []

  @classmethod
  def load(cls, name, driver=None, gce_obj=None):
    if driver:
      try:
        assert name == gce_obj.name, "%s != %s" % (name, gce_obj.name)
        return cls.load(gce_obj=self._gce_obj_get(self, driver))
      except ResourceNotFoundError:
        pass

    obj = cls(name, sentinal=cls._sentinal)
    cached = memcache.get(obj._cache_key())
    if cached:
      obj.update(cached)

    if gce_obj:
      obj.update_from_gce(gce_obj)

    memcache.set(obj._cache_key(), obj, time=120)
    return obj

  def __init__(self, name, sentinal=None):
    assert sentinal is self._sentinal
    dict.__init__(self)
    self.name = name
    self.status = "IMAGINARY"
    self.create_time = inf

  def __eq__(self, other):
    return type(self) == type(other) and self.name == other.name

  def exists(self):
    return self.create_time != inf

  def ready(self):
    return self.status == "READY"

  # ---------------------------------

  def destroy(self, driver):
    assert self.exists()
    assert self.ready()
    TimerLog.log(self, "DESTROY")
    self._gce_obj_destory(driver, self._gce_obj_get(driver))


class Disk(GCEObject):
  # Functions to get/destroy stuff on gce
  def _gce_obj_get(self, driver):
    return driver.ex_get_volume(self.name)

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    return driver.destroy_volume(gce_obj)

  # ---------------------------------

  def create(self, driver, from_snapshot):
    TimerLog.log(self, "CREATE")
    self.update_from_gce(
        driver.create_volume(size=None, name=self.name, snapshot=from_snapshot, ex_disk_type='pd-ssd'))


class Snapshot(GCEObject):
  # Functions to get/destroy stuff on gce
  def _gce_obj_get(self, driver):
    return driver.ex_get_snapshot(self.name)

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    return driver.destroy_volume_snapshot(gce_obj)

  @staticmethod
  def _gce_obj_status(gce_obj):
    # For some reason snapshot status is only available via .status rather than
    # .extra['status']!?
    return gce_obj.status

  # ---------------------------------

  def create(self, driver, from_disk):
    TimeLog.log(self, "CREATE")
    self.update_from_gce(
       driver.create_volume_snapshot(driver.ex_get_volume(from_disk), self.name))



class Instance(GCEObject):
  # Functions to get/destroy stuff on gce
  def _gce_obj_get(self, driver):
    return driver.ex_get_node(self.name)

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    return driver.destroy_node(gce_obj)

  def update_from_gce(self, gce_obj):
    GCEObject.update_from_gce(self, gce_obj)
    self.public_ips = gce_obj.public_ips

    metadata = {}
    for d in gce_obj.extra['metadata']['items']:
      v = d['value']
      if v.startswith('{') or v.startswith('[') or v.startswith('"'):
        try:
          v = simplejson.loads(v)
        except:
          pass
      metadata[d['key']] = d['value']
    self.metadata = metadata

    self.disks = []
    for d in gce_obj.extra['disks']:
      if d['kind'] != 'compute#attachedDisk':
        continue

      disk = Disk.load(d['deviceName'])
      self.disks.append(disk)

  # ---------------------------------

  def __init__(self, name, sentinal=None):
    GCEObject.__init__(self, name, sentinal)
    self.public_ips = []
    self.disks = []
    self.metadata = {}

  def ready(self):
    if not GCEObject.ready(self):
      return False

    if not self.fetch():
      return False

    return True

  def attached(self, disk):
    return disk in self.disks

  def fetch(self, name=""):
    if name:
      name = '/%s' % name

    if not self.public_ips:
      return None

    try:
      return urllib2.urlopen(
          "http://%s/tmp%s" % (
              self.public_ips[0], name)).read()
    except (urllib2.HTTPError, urllib2.URLError) as e:
      return None

  # ---------------------------------

  MACHINE_TYPE = 'n1-standard-2'
  BOOT_IMAGE = 'boot-image-wip-2'
  STARTUP_SCRIPT = 'metadata_watcher.py'
  TAGS = ('http-server',)

  def create(self, driver):
    TimerLog.log(self, "CREATE")

    self.update_from_gce(driver.deploy_node(
      self.name,
      size=self.MACHINE_TYPE,
      image=self.IMAGE,
      script=self.STARTUP_SCRIPT,
      ex_tags=self.TAGS))

  def attach(self, driver, disk, mode):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists(driver)
    assert disk.ready(driver)

    TimerLog.log(self, "ATTACH", disk, mode)

    driver.attach_volume(
      node=self._gce_obj_get(driver),
      volume=disk._gce_obj_get(driver),
      device=disk.name,
      ex_mode=mode)

  def detach(self, driver, disk):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists(driver)
    assert disk.ready(driver)
    assert disk in self.disks(driver)

    driver.detach_volume(
      volume=disk._gce_obj_get(driver),
      ex_node=self._gce_obj_get(driver))

  def set_metadata(self, driver, data=None, **kw):
    metadata = copy.deepcopy(self.metadata)
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
    driver.ex_set_node_metadata(self._gce_obj_get(driver), metadata)

