import webapp2

from tasklet_time_log import TaskletTimer


class ClearTimersHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Clear timers?<br>This will not cancel the tasklets.<br>')
    for timer in TaskletTimer.query():
      self.response.write(' - %s<br>' % timer.tid())
    self.response.write('<form method="POST"><input type="submit"></input></form>')

  def post(self):
    self.response.write('Cleared timers:<br>')
    for timer in TaskletTimer.query():
      self.response.write(' - %s<br>' % timer.tid())
      timer.key.delete()
