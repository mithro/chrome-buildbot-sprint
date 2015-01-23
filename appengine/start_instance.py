
import libcloud_gae
import webapp2
import time


class StartInstanceHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    node = libcloud_gae.new_driver().deploy_node(
        'appengine-created-instance',
        size=libcloud_gae.MACHINE_TYPE,
        image=libcloud_gae.BOOT_IMAGE,
        script=libcloud_gae.STARTUP_SCRIPT)
    self.response.write('%s %s' % (time.time() - start, node))


APP = webapp2.WSGIApplication([
  ('/start-instance/?', StartInstanceHandler),
], debug=True)
