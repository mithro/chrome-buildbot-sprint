import datetime
import stages


class TaskletDuration(ndb.Model):
  tid = ndb.StringProperty(required=True)
  start_time = ndb.DateTimeProperty(required=True)
  stop_time = ndb.DateTimeProperty(required=True)
  seconds = ndb.FloatProperty(required=True)


class TaskletTimer(ndb.Model):
  stage_class = ndb.StringProperty(required=True)
  stage_previous_commit = ndb.StringProperty(required=True)
  stage_current_commit = ndb.StringProperty(required=True)
  tid = ndb.StringProperty(required=True)
  start_time = ndb.DateTimeProperty(auto_now=True)

  def stop(self):
    stop_time = datetime.datetime.utcnow()
    TaskletDuration(
      tid=self.tid,
      start_time=self.start_time,
      stop_time=stop_time,
      seconds=(stop_time - start_time).total_seconds()
    ).put()
    self.key.delete_async()


class TaskletTimeLog(object):
  @staticmethod
  def start_timer(tasklet):
    TaskletTimer(
      stage_class=tasklet.stage.__class__.__name__,
      stage_previous_commit=tasklet.stage.previous_commit,
      stage_current_commit=tasklet.stage.current_commit,
      tid=tasklet.tid,
    ).put()

  @staticmethod
  def update_timers(driver):
    timer_map = dict((timer.tid, timer) for timer in TaskletTimer.query())
    stage_set = {(timer.stage_class, timer.stage_previous_commit, timer.stage_current_commit) for timer in timer_map.values()}
    for stage_class, previous_commit, current_commit in stage_set:
      for tasklet in getattr(stages, stage_class)(previous_commit, current_commit).tasklets():
        if tasklet.tid in timer_map and tasklet.is_finished(driver):
          timer_map.popitem(tasklet.tid).stop()
