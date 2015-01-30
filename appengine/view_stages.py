import jinja2
import logging
import os
import time
import webapp2

from cache import CACHE
from current_stages import get_current_stages
from experiment import get_current_experiment


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'view-stages.html')).read())


class ViewStagesHandler(webapp2.RequestHandler):
  def get(self):
    in_progress = []
    pending = []
    for stage in get_current_stages():
      if not stage.is_finished():
        if stage.is_startable():
          in_progress.append(stage)
        else:
          pending.append(stage)
    self.response.out.write(
      TEMPLATE_STAGE.render(
        experiment=get_current_experiment(),
        stages_in_progress=in_progress,
        stages_pending=pending,
      )
    )
