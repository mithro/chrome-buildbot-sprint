#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

from google.appengine.api import taskqueue

from objects import Instance
from objects import Disk
from objects import Snapshot
from tasklet_time_log import TaskletTimeLog
import libcloud_gae
import webapp2
import time

from cache import CACHE

PAGE_TEMPLATE = """\
<html>
  <head>
    <meta http-equiv="refresh" content="30">
    <title>{}</title>
  </head>
  <body>
  <h1>{}</h1>
  <tt>time: {}</tt><br>
  {}
  </body>
</html>
"""

PAGE_SUMMARY_TEMPLATE = """\
  <h1>Instances:</h1>
  <tt>{}</tt>
  <h1>Disks:</h1>
  <tt>{}</tt>
  <h1>Snapshots:</h1>
  <tt>{}</tt>
"""

PAGE_LINK_TEMPLATE = """\
  <a href="/poll_gce/memcache/{}:{}">{}</a>
"""


def generate_summary(instance_names=[], disk_names=[], snapshot_names=[]):
  if not instance_names:
    instance_names = []
  if not disk_names:
    disk_names = []
  if not snapshot_names:
    snapshot_names = []
  return PAGE_SUMMARY_TEMPLATE.format(
    '<br>\n'.join([PAGE_LINK_TEMPLATE.format('instance', i, i) for i in instance_names]),
    '<br>\n'.join([PAGE_LINK_TEMPLATE.format('disk', i, i) for i in disk_names]),
    '<br>\n'.join([PAGE_LINK_TEMPLATE.format('snapshot', i, i) for i in snapshot_names]),
  )


class ScheduleHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()

    for c in xrange(0, 60, 20):
        taskqueue.add(url='/poll_gce/do',
                      method='GET',
                      countdown=c,
                      queue_name='poll')

    result = PAGE_TEMPLATE.format(
        'poll_gce/schedule',
        'Scheduled poll_gce/do',
        time.time() - start,
        "",
    )

    self.response.write(result)


class PollGceHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    driver = libcloud_gae.new_driver()
    nodes = driver.list_nodes()
    volumes = driver.list_volumes()
    snapshots = driver.ex_list_snapshots()

    instance_names = [n.name for n in nodes]
    disk_names = [d.name for d in volumes]
    snapshot_names = [s.name for s in snapshots]

    CACHE.set('gce_instances', instance_names, time=60)
    CACHE.set('gce_disks', disk_names, time=60)
    CACHE.set('gce_snapshots', snapshot_names, time=60)

    for node in nodes:
        Instance.load(node.name, gce_obj=node)

    for volume in volumes:
        Disk.load(volume.name, gce_obj=volume)

    for snapshot in snapshots:
        Snapshot.load(snapshot.name, gce_obj=snapshot)

    TaskletTimeLog.update_timers()

    result = PAGE_TEMPLATE.format(
        'poll_gce/do',
        'Polled GCE',
        time.time() - start,
        generate_summary(instance_names, disk_names, snapshot_names),
    )

    self.response.write(result)


class ReadMemcacheHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    instance_names = CACHE.get("gce_instances")
    disk_names = CACHE.get("gce_disks")
    snapshot_names = CACHE.get("gce_snapshots")

    result = PAGE_TEMPLATE.format(
        'poll_gce/memcache',
        'Read from memcache',
        time.time() - start,
        generate_summary(instance_names, disk_names, snapshot_names),
    )

    self.response.write(result)

class ReadMemcacheEntityHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()

    path = self.request.path
    pre_path, _, name = path.partition(':')
    _, _, entity_type = pre_path.rpartition('/')
    key = entity_type + ':' + name

    result = PAGE_TEMPLATE.format(
        key,
        'memcache: ' + key,
        time.time() - start,
        CACHE.get(key),
    )

    self.response.write(result)
