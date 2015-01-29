import logging
import webapp2

from google.appengine.api import taskqueue

from current_stages import get_current_stages


TEMPLATE = '''\
<meta http-equiv="refresh" content="30">
<pre>
Things started:
%s
</pre>
'''


class RunStagesHandler(webapp2.RequestHandler):
  def get(self):
    things_started = []
    for stage in get_current_stages():
      if stage.needs_cleanup():
        taskqueue.add(
            url='/cleanup/sync/previous-%s/current-%s' % (stage.previous_commit, stage.current_commit),
            method='GET',
            queue_name='run',
        )
        things_started.append("Cleanup of %s" % stage.stage_id)
      elif not stage.is_finished():
        for tasklet in stage.tasklets:
          if tasklet.can_run():
            stage_url = '/stage/sync/previous-%s/current-%s' % (stage.previous_commit, stage.current_commit)
            taskqueue.add(
                url='%s?go=%s' % (stage_url, tasklet.tid),
                method='GET',
                queue_name='run',
            )
            things_started.append("For %s starting %s" % (stage.stage_id, tasklet.tid))
    if things_started:
      logging.debug(things_started)
    self.response.out.write(TEMPLATE % ''.join(' - %s\n' % thing for thing in things_started))


APP = webapp2.WSGIApplication([
  ('/run_stages/?', RunStagesHandler),
], debug=True)
