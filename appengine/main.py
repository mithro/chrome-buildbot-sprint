import webapp2

from callback import CallbackHandler
from clear_timers import ClearTimersHandler
from poll_gce import (
  ScheduleHandler,
  PollGceHandler,
  ReadMemcacheEntityHandler,
  ReadMemcacheHandler,
)
from run_stages import RunStagesHandler
from stage_status import StageCleanupHandler
from stage_status import StageStatusHandler
from test_results import TestResultsHandler
from timeline import TimelineHandler
from view_stages import ViewStagesHandler


APP = webapp2.WSGIApplication([
  ('/callback/?', CallbackHandler),
  ('/stage/(.*)/previous-(.*)/current-(.*)', StageStatusHandler),
  ('/cleanup/(.*)/previous-(.*)/current-(.*)', StageCleanupHandler),
  ('/clear_timers/?', ClearTimersHandler),

  ('/poll_gce/schedule', ScheduleHandler),
  ('/poll_gce/do', PollGceHandler),
  ('/poll_gce/memcache/\w+:.*', ReadMemcacheEntityHandler),
  ('/poll_gce/.*', ReadMemcacheHandler),

  ('/run_stages/?', RunStagesHandler),
  ('/test_results/.*', TestResultsHandler),
  ('/timeline/?', TimelineHandler),
  ('/view_stages/?', ViewStagesHandler),
], debug=True)
