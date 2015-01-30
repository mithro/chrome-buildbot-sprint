import jinja2
import os
import webapp2
import logging

from current_stages import get_current_stages


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'view-stages.html')).read())


import time

class ViewStagesHandler(webapp2.RequestHandler):
  def get(self):
    from cache import CACHE
    t = time.time()
    stages = [
        s for s in get_current_stages() if not s.is_finished() and s.is_startable()]
    logging.debug("Finished get stages in %s", time.time() - t)
    self.response.out.write(TEMPLATE_STAGE.render(stages=stages))
