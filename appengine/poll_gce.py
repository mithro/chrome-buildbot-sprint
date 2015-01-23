
from google.appengine.api import memcache
from google.appengine.api import taskqueue

import libcloud_gae
import webapp2
import time

PAGE_TEMPLATE = """\
<html>
  <head>
    <title>{}</title>
  </head>
  <body>
  <h1>{}</h1>
  <tt>time: {}</tt><br>
  {}
  </body>
</html>
"""

PAGE_DATA_TEMPLATE = """\
  <h1>Instances:</h1>
  <tt>{}</tt>
  <h1>Disks:</h1>
  <tt>{}</tt>
  <h1>Snapshots:</h1>
  <tt>{}</tt>
"""

class ScheduleHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()

    # Cron schedules us once per minute, so issue 6 tasks to get one per 10s.
    for c in xrange(6):
        taskqueue.add(url='/poll_gce/do',
                      method='GET',
                      countdown=c)

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


    memcache.set_multi({ "gce_instances": instance_names,
                         "gce_disks": disk_names,
                         "gce_snapshots": snapshot_names },
                         time=120)

    result = PAGE_TEMPLATE.format(
        'poll_gce/do',
        'Polled GCE',
        time.time() - start,
        PAGE_DATA_TEMPLATE.format(
            '<br>\n'.join(instance_names),
            '<br>\n'.join(disk_names),
            '<br>\n'.join(snapshot_names),
        ),
    )

    self.response.write(result)


class ReadMemcacheHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    instance_names = memcache.get("gce_instances")
    if not instance_names:
        instance_names = []
    disk_names = memcache.get("gce_disks")
    if not disk_names:
        disk_names = []
    snapshot_names = memcache.get("gce_snapshots")
    if not disk_names:
        disk_names = []

    result = PAGE_TEMPLATE.format(
        'poll_gce/memcache',
        'Read from memcache',
        time.time() - start,
        PAGE_DATA_TEMPLATE.format(
            '<br>\n'.join(instance_names),
            '<br>\n'.join(disk_names),
            '<br>\n'.join(snapshot_names),
        ),
    )

    self.response.write(result)


APP = webapp2.WSGIApplication([
  ('/poll_gce/schedule', ScheduleHandler),
  ('/poll_gce/do', PollGceHandler),
  ('/poll_gce/.*', ReadMemcacheHandler),
], debug=True)
