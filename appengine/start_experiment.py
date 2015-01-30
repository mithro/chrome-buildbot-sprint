import webapp2

from experiment import (
  get_current_experiment,
  start_experiment,
)


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
