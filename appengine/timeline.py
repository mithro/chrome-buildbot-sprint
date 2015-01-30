from datetime import (
  datetime,
  timedelta,
)
import webapp2

from tasklet_time_log import (
  TaskletDuration,
  TaskletTimer,
)

from experiment import get_current_experiment


VIEW_HOURS = 24
TEMPLATE = '''\
<meta http-equiv="refresh" content="30">
<pre>
Current time: %(current_time)s

Running tasklets: <a href="/clear_timers">[clear]</a>
%(running_tasklets)s
Completed tasklets in the last %(duration).2f hours:
%(completed_tasklets)s
</pre>
'''


def start_time_sorted(query):
  return sorted(query, cmp=lambda x,y: cmp(x.start_time, y.start_time))


class TimelineHandler(webapp2.RequestHandler):
  def get(self):
    experiment = get_current_experiment()
    if experiment:
      duration = experiment.elapsed()
    else:
      duration = timedelta(hours=VIEW_HOURS)
    now = datetime.utcnow()
    timers = start_time_sorted(TaskletTimer.query())
    durations = start_time_sorted(TaskletDuration.query().filter(
      TaskletDuration.stop_time >= now - duration,
    ))
    self.response.write(TEMPLATE % {
      'current_time': now,
      'running_tasklets': ''.join(' - %s %s (%ds)\n' % (timer.start_time, timer.tid(), (now - timer.start_time).total_seconds()) for timer in timers),
      'completed_tasklets': ''.join(' - %s %s (%ds)\n' % (duration.start_time, duration.tid, duration.seconds) for duration in durations),
      'duration': duration.total_seconds() / 3600,
    })

