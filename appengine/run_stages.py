import os

import webapp2
import jinja2
from google.appengine.api import taskqueue

import helpers
import objects
import stages


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'stage-overview.html')).read())


# Earliest commit comes first
COMMIT_LIST = (
  'fa1651193bf94120',
  '32cbfaa6478f66b9',
  '1874cd207f996341',
  '863dc8b59882bf44',
)


class RunStagesHandler(webapp2.RequestHandler):
  def get(self):
    previous_commit = COMMIT_LIST[0]
    previous_snapshot_name = helpers.SnapshotName(previous_commit, "src")
    assert objects.Snapshot.load(previous_snapshot_name).ready(), previous_snapshot_name

    things_started = []

    stage_list = []
    for current_commit in COMMIT_LIST[1:]:
      stage = stages.SyncStage(previous_commit, current_commit)
      stage.url = '/stage/sync/previous-%s/current-%s' % (previous_commit, current_commit)

      if stage.is_finished():
        cleanup_url = '/cleanup/sync/previous-%s/current-%s' % (previous_commit, current_commit)
        taskqueue.add(
            url=cleanup_url,
            method='GET',
            queue_name='run',
        )
        things_started.append("Cleanup of %s" % stage.stage_id)
      else:
        for tasklet in stage.tasklets():
          if tasklet.can_run():
            taskqueue.add(
                url='%s?go=%s' % (stage.url, tasklet.tid),
                method='GET',
                queue_name='run',
            )
            things_started.append("For %s starting %s" % (stage.stage_id, t.tid))
      stage_list.append(stage)
      previous_commit = current_commit

    self.response.out.write(TEMPLATE_STAGE.render(stages=stage_list, things_started=things_started))


APP = webapp2.WSGIApplication([
  ('/run_stages/?', RunStagesHandler),
], debug=True)
