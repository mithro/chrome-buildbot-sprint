from datetime import datetime
import webapp2

from tasklet_time_log import (
  TaskletDuration,
  TaskletTimer,
)


def start_time_sorted(model):
  return sorted(model.query(), cmp=lambda x,y: cmp(x.start_time, y.start_time))


class TimelineHandler(webapp2.RequestHandler):
  def get(self):
    now = datetime.now()
    self.response.write('Current time: %s\n' % now)
    self.response.write('\n\n')
    self.response.write('Running tasklets:\n')
    for timer in start_time_sorted(TaskletTimer):
      self.response.write(' - %s %s (%ds)\n' % (timer.start_time, timer.tid(), (now - timer.start_time).total_seconds()))
    self.response.write('\n\n')
    self.response.write('Completed tasklets:\n')
    for duration in start_time_sorted(TaskletDuration):
      self.response.write(' - %s %s (%ds)\n' % (duration.start_time, duration.tid, duration.seconds))
    self.response.headers.add_header('Content-Type', 'text/plain')


APP = webapp2.WSGIApplication([
  ('/timeline/?', TimelineHandler),
], debug=True)
