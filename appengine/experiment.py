from datetime import (
  datetime,
  timedelta,
)

from google.appengine.ext import ndb


EXPERIMENT_DURATION = timedelta(days=1)


class Experiment(ndb.Model):
  start_time = ndb.DateTimeProperty(required=True)
  stop_time = ndb.DateTimeProperty(required=True)

  def elapsed(self):
    return datetime.utcnow() - self.start_time

  def elapsed_hours(self):
    return self.elapsed().total_seconds() / 3600

  def remaining_hours(self):
    return (self.stop_time - datetime.utcnow()).total_seconds() / 3600


def get_current_experiment():
  now = datetime.utcnow()
  return Experiment.query().filter(
    Experiment.stop_time > now,
  ).get()


def start_experiment():
  experiment = get_current_experiment()
  if experiment:
    experiment.key.delete()
  now = datetime.utcnow()
  Experiment(
    start_time=now,
    stop_time=now + EXPERIMENT_DURATION,
  ).put()
