#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import copy
import time
import random
import string
import urllib2

try:
  import simplejson
except:
  import json as simplejson

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
  @staticmethod
  def _gce_obj_get(driver, name):
    raise NotImplementedError()

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    raise NotImplementedError()

  @staticmethod
  def _gce_obj_status(gce_obj):
    return gce_obj.extra['status']

  def update_from_gce(self, gce_obj):
    assert self.name == gce_obj.name, "%s != %s" % (self.name, gce_obj.name)
    self.name = gce_obj.name
    self.create_time = parse_time(gce_obj.extra['creationTimestamp'])
    self.status = self._gce_obj_status(gce_obj)

  # ---------------------------------
  _sentinal = []

  @classmethod
  def load(cls, name, driver=None, gce_obj=None):
    if driver:
      try:
        return cls.load(name, gce_obj=cls._gce_obj_get(driver, name))
      except ResourceNotFoundError:
        pass

    obj = cls(name, sentinal=cls._sentinal)
    cached = memcache.get(obj._cache_key())
    if cached:
      obj.update(cached)

    if gce_obj:
      obj.update_from_gce(gce_obj)

    obj.store()
    return obj

  def store(self):
    memcache.set(self._cache_key(), self, time=12000)

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
    try:
      self._gce_obj_destory(driver, self._gce_obj_get(driver, self.name))
    except ResourceNotFoundError:
      pass
    memcache.delete(self._cache_key())


class Disk(GCEObject):
  # Functions to get/destroy stuff on gce
  @staticmethod
  def _gce_obj_get(driver, name):
    return driver.ex_get_volume(name)

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    return driver.destroy_volume(gce_obj)

  # ---------------------------------

  def create(self, driver, from_snapshot):
    self.update_from_gce(
        driver.create_volume(size=None, name=self.name, snapshot=from_snapshot, ex_disk_type='pd-ssd'))


class Snapshot(GCEObject):
  # Functions to get/destroy stuff on gce
  @staticmethod
  def _gce_obj_get(driver, name):
    return driver.ex_get_snapshot(name)

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
    self.update_from_gce(
       driver.create_volume_snapshot(driver.ex_get_volume(from_disk), self.name))



class Instance(GCEObject):
  # Functions to get/destroy stuff on gce
  @staticmethod
  def _gce_obj_get(driver, name):
    return driver.ex_get_node(name)

  @staticmethod
  def _gce_obj_destory(driver, gce_obj):
    return driver.destroy_node(gce_obj)

  def update_from_gce(self, gce_obj):
    GCEObject.update_from_gce(self, gce_obj)
    self.public_ips = gce_obj.public_ips

    metadata = {}
    if 'metadata' in gce_obj.extra and 'items' in gce_obj.extra['metadata']:
      for d in gce_obj.extra['metadata']['items']:
        v = d['value']
        if v.startswith('{') or v.startswith('[') or v.startswith('"'):
          try:
            v = simplejson.loads(v)
          except ImportError:
            pass
        metadata[d['key']] = v
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
    if self.status != "RUNNING":
      return False

    #if not self.fetch():
    #  return False

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
  BOOT_IMAGE = 'boot-image-win-4'
  STARTUP_SCRIPT_URL = 'https://raw.githubusercontent.com/mithro/chrome-buildbot-sprint/master/metadata_watcher.py'
  WINDOWS_STARTUP_SCRIPT = 'windows-startup-script.ps1'
  TAGS = ('http-server',)

  def create(self, driver):
    self.update_from_gce(driver.create_node(
      self.name,
      size=self.MACHINE_TYPE,
      image=self.BOOT_IMAGE,
      ex_tags=self.TAGS,
      ex_metadata={'startup-script-url': self.STARTUP_SCRIPT_URL,
                   'windows-startup-script-ps1': open(self.WINDOWS_STARTUP_SCRIPT).read(),
                   'gce-initial-windows-user': 'delta-trees-830',
                   'gce-initial-windows-password': ''.join([random.choice(string.ascii_letters) for u in range(8)]),
                   },
      ))

  def attach(self, driver, disk, mode):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists()
    assert disk.ready()

    driver.attach_volume(
      node=self._gce_obj_get(driver, self.name),
      volume=disk._gce_obj_get(driver, disk.name),
      device=disk.name,
      ex_mode=mode)

  def detach(self, driver, disk):
    assert self.exists()
    assert self.ready()
    assert isinstance(disk, Disk)
    assert disk.exists()
    assert disk.ready()
    assert disk in self.disks

    driver.detach_volume(
      volume=disk._gce_obj_get(driver, disk.name),
      ex_node=self._gce_obj_get(driver, self.name))

  def set_metadata(self, driver, data={}, **kw):
    metadata = copy.deepcopy(self.metadata)
    metadata.update(data)
    metadata.update(kw)
    for key in metadata.keys():
      v = metadata[key]
      if isinstance(v, (int, long, float, str, unicode)):
        continue
      elif isinstance(metadata[key], (list, dict)):
        metadata[key] = simplejson.dumps(metadata[key])
      else:
        raise TypeError("Can't set metadata key %s to %r" % (key, v))
    while not driver.ex_set_node_metadata(self._gce_obj_get(driver, self.name), metadata):
      time.sleep(1)

    gce_obj = self._gce_obj_get(driver, self.name)
    self.update_from_gce(gce_obj)
    self.store()
