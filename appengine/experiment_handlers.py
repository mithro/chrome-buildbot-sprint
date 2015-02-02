from datetime import datetime
import webapp2

from experiment import (
  Experiment,
  get_current_experiment,
  start_experiment,
)
from helpers import (
  str_datetime,
  str_timedelta,
)
from tasklet_time_log import (
  TaskletDuration,
  TaskletTimer,
)


EXPERIMENT_LINK = '<a href="/view_experiment/%s">%s to %s</a>'


class StartExperimentHandler(webapp2.RequestHandler):
  def get(self):
    experiment = get_current_experiment()
    if not experiment:
      self.response.write('Start new experiment?<br>')
    else:
      self.response.write('Restart current experiment (%.2f hours left)?<br>' % experiment.remaining_hours())
    self.response.write('<form method="POST"><input type="submit"></input></form>')

  def post(self):
    self.response.write('Started new experiment.')
    start_experiment()


class ViewExperimentsHandler(webapp2.RequestHandler):
  def get(self):
    current_experiment = get_current_experiment()
    if current_experiment:
      self.response.write('Current experiment: ')
      self.response.write(EXPERIMENT_LINK % (
        current_experiment.key.integer_id(),
        current_experiment.start_time,
        current_experiment.stop_time,
      ))
      self.response.write('<br>')

    header_added = False
    for experiment in Experiment.query():
      if current_experiment and current_experiment.key == experiment.key:
        continue
      if not header_added:
        self.response.write('Past experiments:<br>')
        header_added = True
      self.response.write(EXPERIMENT_LINK % (
        experiment.key.integer_id(),
        experiment.start_time,
        experiment.stop_time,
      ))
      self.response.write('<br>')


class ViewExperimentHandler(webapp2.RequestHandler):
  def get(self, experiment_id):
    experiment = Experiment.get_by_id(long(experiment_id))
    assert experiment, 'Experiment key must be valid'
    self.response.write('Experiment from %s to %s.<br>' % (experiment.start_time, experiment.stop_time))
    self.response.write('Elapsed: %s<br>' % (str_timedelta(experiment.elapsed())))
    self.response.write('Remaining: %s<br>' % (str_timedelta(experiment.remaining())))
    items = []
    timers = TaskletTimer.query().filter(
      TaskletTimer.start_time >= experiment.start_time,
      TaskletTimer.start_time < experiment.stop_time,
    )
    now = datetime.utcnow()
    for timer in timers:
      items.append({
        'id': timer.tid(),
        'group': Stage.commit_from_stage_id(timer.tid()),
        'content': '%s (running)' % timer.tid(),
        'start': str_datetime(timer.start_time()),
        'end': str_datetime(now),
      })
    durations = TaskletDuration.query().filter(
      TaskletDuration.start_time >= experiment.start_time,
      TaskletDuration.start_time < experiment.stop_time,
    )
    for duration in durations:
      items.append({
        'id': duration.tid,
        'group': Stage.commit_from_stage_id(duration.tid),
        'content': duration.tid,
        'start': str_datetime(duration.start_time),
        'end': str_datetime(duration.stop_time),
      })
    items.sort(cmp=lambda x,y:cmp(x['start'], y['start']))
    groups = []
    commits = set()
    for item in items:
      commit = item['group']
      if commit in commits:
        continue
      commits.add(commit)
      groups.append({
        'id': commit,
        'content': commit,
      })
    self.response.write(str(items))
    self.response.write(str(groups))
