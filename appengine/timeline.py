from datetime import (
  datetime,
  timedelta,
)
import webapp2

from tasklet_time_log import (
  TaskletDuration,
  TaskletTimer,
)


VIEW_HOURS = 4


def start_time_sorted(query):
  return sorted(query, cmp=lambda x,y: cmp(x.start_time, y.start_time))


class TimelineHandler(webapp2.RequestHandler):
  def get(self):
    now = datetime.utcnow()
    self.response.write('Current time: %s\n' % now)
    self.response.write('\n\n')
    self.response.write('Running tasklets:\n')
    for timer in start_time_sorted(TaskletTimer.query()):
      current_duration = (now - timer.start_time).total_seconds()
      self.response.write(' - %s %s (%ds)\n' % (timer.start_time, timer.tid(), current_duration))
    self.response.write('\n\n')
    self.response.write('Completed tasklets in the last %s hours:\n' % VIEW_HOURS)
    durations = TaskletDuration.query().filter(
      TaskletDuration.stop_time >= now - timedelta(hours=VIEW_HOURS),
    )
    for duration in start_time_sorted(durations):
      self.response.write(' - %s %s (%ds)\n' % (duration.start_time, duration.tid, duration.seconds))
    self.response.headers.add_header('Content-Type', 'text/plain')


APP = webapp2.WSGIApplication([
  ('/timeline/?', TimelineHandler),
], debug=True)
