import logging
import jinja2
import os
import webapp2

from google.appengine.api import taskqueue

from current_stages import get_current_stages


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'stage-overview.html')).read())


class ViewStagesHandler(webapp2.RequestHandler):
  def get(self):
    self.response.out.write(TEMPLATE_STAGE.render(stages=get_current_stages()))


APP = webapp2.WSGIApplication([
  ('/view_stages/?', ViewStagesHandler),
], debug=True)
