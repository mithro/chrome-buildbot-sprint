import jinja2
import os
import webapp2

from current_stages import get_current_stages


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'stage-overview.html')).read())


class ViewStagesHandler(webapp2.RequestHandler):
  def get(self):
    stages = get_current_stages()
    for i, stage in enumerate(stages):
      if not stage.is_finished():
        break
    self.response.out.write(TEMPLATE_STAGE.render(stages=stages[max(i-1, 0):i+1]))


APP = webapp2.WSGIApplication([
  ('/view_stages/?', ViewStagesHandler),
], debug=True)
