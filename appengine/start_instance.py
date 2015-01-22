import sys
sys.path.append("third_party/backports")
sys.path.append("third_party/libcloud")

import webapp2

from libcloud.common.google import ResourceNotFoundError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.ssh import ParamikoSSHClient as SSHClient

NAMESPACE = 'appengine'

class StartInstanceHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('instance')


APP = webapp2.WSGIApplication([
  ('/start-instance/?', StartInstanceHandler),
], debug=True)
