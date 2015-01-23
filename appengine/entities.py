
import sys
sys.path.append("third_party/python-dateutil-1.5")

import calendar
import dateutil.parser
import time
from google.appengine.api import memcache
from libcloud_gae import ResourceNotFoundError


def parse_time(timestamp_str):
  dt = dateutil.parser.parse(timestamp_str)
  return calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond


class DictEntity(dict):

  def __init__(self):
    dict.__init__(self)

  def __setattr__(self, key, value):
    self[key] = value

  def __getattr__(self, key):
    return self[key]

  def __setstate__(self, state):
    self.__dict__ = state

  def __getstate__(self):
    return self.__dict__


class Disk(DictEntity):

  @staticmethod
  def from_gce(gce_volume):
    disk = Disk()
    disk['name'] = gce_volume.name

    try:
      disk['create_time'] = parse_time(gce_volume.extra['creationTimestamp'])
    except ResourceNotFoundError:
      disk['create_time'] = inf

    try:
      disk['status'] = gce_volume.extra['status']
    except ResourceNotFoundError:
      disk['status'] = inf

    memcache.set(Disk.get_cache_key(disk.name), disk)
    return disk

  @staticmethod
  def load(name, driver):
    cached = memcache.get(Disk.get_cache_key(name))
    if cached:
      disk = Disk()
      disk.update(cached)
      return disk

    return Disk.from_gce(driver.ex_get_volume(name))

  @staticmethod
  def get_cache_key(name):
    return 'disk:' + name;

  def exists(self):
    return self.create_time

  def ready(self):
    if self.status != "READY":
      return inf

    return TimerLog.log(self, "READY")

  def create(self, driver, from_snapshot):
    TimerLog.log(self, "CREATE")
    self.update(Disk.from_gce(
      driver.create_volume(size=None, name=self.name, snapshot=from_snapshot, ex_disk_type='pd-ssd')))

  def destroy(self, driver):
    assert self.exists()
    assert self.ready()
    TimerLog.log(self, "DESTROY")
    driver.destroy_volume(driver.ex_get_volume(self.name))


class Snapshot(DictEntity):

  @staticmethod
  def from_gce(gce_snapshot):
    snapshot = Snapshot()
    snapshot['name'] = gce_snapshot.name

    try:
      snapshot['create_time'] = parse_time(gce_snapshot.extra['creationTimestamp'])
    except ResourceNotFoundError:
      snapshot['create_time'] = inf

    try:
      snapshot['status'] = gce_snapshot.status
    except ResourceNotFoundError:
      snapshot['status'] = inf

    memcache.set(Snapshot.get_cache_key(snapshot.name), snapshot)
    return snapshot

  @staticmethod
  def load(name, driver):
    cached = memcache.get(Snapshot.get_cache_key(name))
    if cached:
      snapshot = Snapshot()
      snapshot.update(cached)
      return snapshot

    return Snapshot.from_gce(driver.ex_get_snapshot(name))

  @staticmethod
  def get_cache_key(name):
    return 'snapshot:' + name;

  def exists(self, driver):
    return self.create_time

  def ready(self, driver):
    if self.status != "READY":
      return inf

    return TimerLog.log(self, "READY")

  def create(self, driver, from_disk):
    TimeLog.log(self, "CREATE")
    self.update(Snapshot.from_gce(
        driver.create_volume_snapshot(driver.ex_get_volume(from_disk), self.name)))

  def destroy(self, driver):
    assert self.exists(driver)
    assert self.ready(driver)
    TimerLog(self, "DESTROY")
    driver.destroy_volume_snapshot(driver.ex_get_snapshot(self.name))
