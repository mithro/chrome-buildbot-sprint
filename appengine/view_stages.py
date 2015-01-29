import jinja2
import os
import webapp2

from current_stages import get_current_stages


TEMPLATE_STAGE = jinja2.Template(open(os.path.join(os.path.dirname(__file__), 'view-stages.html')).read())


class ViewStagesHandler(webapp2.RequestHandler):
  def get(self):
    self.response.out.write(
      TEMPLATE_STAGE.render(
        stages = get_current_stages()
        # stages=[
        #   stage
        #   for stage in get_current_stages()
        #   if not stage.is_finished() and any(
        #     tasklet.is_startable() or tasklet.is_running() or tasklet.is_finished()
        #     for tasklet in stage.tasklets
        #   )
        # ]
      )
    )

APP = webapp2.WSGIApplication([
  ('/view_stages/?', ViewStagesHandler),
], debug=True)
