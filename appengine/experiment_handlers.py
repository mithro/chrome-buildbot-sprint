from datetime import datetime
import jinja2
import json
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
from stages import Stage
from tasklet_time_log import (
  TaskletDuration,
  TaskletTimer,
)


EXPERIMENT_LINK = '<a href="/view_experiment/%s">%s to %s</a>'
TEMPLATE_ENV = jinja2.Environment()
TEMPLATE_ENV.filters['str_timedelta'] = str_timedelta
TEMPLATE_ENV.filters['json'] = json.dumps
VIEW_EXPERIMENT_TEMPLATE = TEMPLATE_ENV.from_string(open('view-experiment.html').read())


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
    tasklet_items = []
    def add_item(tid, content_template, start_time, stop_time):
      sid, job = Stage.extract_stage_id(tid)
      stage = '%s-%s' % (Stage.extract_name(sid), Stage.extract_commit(sid))
      tasklet_items.append({
        'id': len(tasklet_items),
        'group': stage,
        'content': content_template % job,
        'start': str_datetime(start_time),
        'end': str_datetime(stop_time),
      })
    now = datetime.utcnow()
    timers = TaskletTimer.query().filter(
      TaskletTimer.start_time >= experiment.start_time,
      TaskletTimer.start_time < experiment.stop_time,
    )
    for timer in timers:
      add_item(timer.tid(), '%s (running)', timer.start_time, now)
    durations = TaskletDuration.query().filter(
      TaskletDuration.start_time >= experiment.start_time,
      TaskletDuration.start_time < experiment.stop_time,
    )
    for duration in durations:
      add_item(duration.tid, '%s', duration.start_time, duration.stop_time)
    stage_tasklet_items = {}
    for item in tasklet_items:
      stage_tasklet_items.setdefault(item['group'], []).append(item)
    stage_items = [{
      'id': stage,
      'content': stage,
      'start': min(item['start'] for item in items),
      'end': max(item['end'] for item in items),
    } for stage, items in stage_tasklet_items.items()]
    self.response.write(VIEW_EXPERIMENT_TEMPLATE.render({
      'experiment': experiment,
      'stage_items': stage_items,
      'stage_tasklet_items': stage_tasklet_items,
    }))
