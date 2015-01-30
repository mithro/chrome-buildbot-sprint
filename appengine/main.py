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
from start_experiment import StartExperimentHandler


APP = webapp2.WSGIApplication([
  ('/poll_gce/schedule', ScheduleHandler),
  ('/poll_gce/do', PollGceHandler),
  ('/poll_gce/memcache/\w+:.*', ReadMemcacheEntityHandler),
  ('/poll_gce/.*', ReadMemcacheHandler),

  ('/callback/?', CallbackHandler),
  ('/stage/(.*)/previous-(.*)/current-(.*)', StageStatusHandler),
  ('/cleanup/(.*)/previous-(.*)/current-(.*)', StageCleanupHandler),
  ('/test_results/.*', TestResultsHandler),
  ('/clear_timers/?', ClearTimersHandler),
  ('/timeline/?', TimelineHandler),
  ('/run_stages/?', RunStagesHandler),
  ('/view_stages/?', ViewStagesHandler),
  ('/start_experiment/?', StartExperimentHandler),
], debug=True)
