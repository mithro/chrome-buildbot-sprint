import os
os.environ['HOME'] = '/FAKE_HOME'

import sys
sys.path.append("third_party/backports")
sys.path.append("third_party/libcloud")

import StringIO, types
GCE_LIBCLOUD_AUTH = StringIO.StringIO('{"access_token": "ya29.AwFYvMsPx9dGypbRq69sDhrtCoRPXNKeeSJZ6LaVyNju31lvjRKnG3adE6k5k3Rfgm9qrmGaOndieQ", "token_type": "Bearer", "expire_time": "2015-01-22T09:55:21Z", "expires_in": 3600}')
StringIO.StringIO.__enter__ = types.MethodType(StringIO.StringIO, lambda self, *args, **kw: self)
StringIO.StringIO.__exit__ = lambda *args, **kw: None
real_open = open
def fake_open(path, mode, files={}):
  if path == "/FAKE_HOME/.gce_libcloud_auth.delta-trees-830":
    if 'w' == mode:
      print "################", "just opened the file"
      return GCE_LIBCLOUD_AUTH
    elif 'r' == mode:
      print "################", GCE_LIBCLOUD_AUTH.getvalue()
      return StringIO.StringIO(GCE_LIBCLOUD_AUTH.getvalue())
    else:
      raise IOError("AHHHH!")
  return real_open(path, mode)
__builtins__['open'] = fake_open

import webapp2
import time

import libcloud.security
libcloud.security.VERIFY_SSL_CERT = False
from libcloud.common.google import ResourceNotFoundError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.ssh import ParamikoSSHClient as SSHClient

# HACK: Extend the request timeout to 10 minutes up from 3 minutes.
from libcloud.common.google import GoogleBaseConnection
GoogleBaseConnection.timeout = 600

PROJECT_ID = 'delta-trees-830'
REGION = 'us-central1'
ZONE = 'us-central1-a'

SERVICE_ACCOUNT_EMAIL = '621016184110-tpkj4skaep6c8ccgolhoheepffasa9kq@developer.gserviceaccount.com'
SERVICE_ACCOUNT_KEY_PATH = 'keys/chrome-buildbot-sprint-c514ee5826d1.pem'
SCOPES = ['https://www.googleapis.com/auth/compute']

MACHINE_TYPE = 'n1-standard-1'
BOOT_IMAGE = 'boot-image-wip'
STARTUP_SCRIPT = 'keys/authorize_ssh_key.sh'
SSH_KEY_PATH = 'keys/gce_bot_rsa'

ComputeEngine = get_driver(Provider.GCE)
def new_driver():
  return ComputeEngine(SERVICE_ACCOUNT_EMAIL,
                       SERVICE_ACCOUNT_KEY_PATH,
                       datacenter=ZONE,
                       project=PROJECT_ID,
                       auth_type='SA',
                       scopes=SCOPES)

class StartInstanceHandler(webapp2.RequestHandler):
  def get(self):
    start = time.time()
    node = new_driver().deploy_node('appengine-created-instance', size=MACHINE_TYPE, image=BOOT_IMAGE, script=STARTUP_SCRIPT)
    self.response.write('%s %s' % (time.time() - start, node))


APP = webapp2.WSGIApplication([
  ('/start-instance/?', StartInstanceHandler),
], debug=True)
