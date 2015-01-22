
import libcloud_gce
import webapp2
import time


class StartInstanceHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    node = libcloud_gce.new_driver().deploy_node(
        'appengine-created-instance',
        size=libcloud_gce.MACHINE_TYPE,
        image=libcloud_gce.BOOT_IMAGE,
        script=libcloud_gce.STARTUP_SCRIPT)
    self.response.write('%s %s' % (time.time() - start, node))


APP = webapp2.WSGIApplication([
  ('/start-instance/?', StartInstanceHandler),
], debug=True)
