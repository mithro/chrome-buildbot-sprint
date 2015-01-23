
import sys
sys.path.append("third_party/backports.ssl_match_hostname-3.4.0.2/src")
sys.path.append("third_party/libcloud")

import patch_libcloud

import libcloud.security
libcloud.security.VERIFY_SSL_CERT = False
from libcloud.common.google import ResourceNotFoundError, ResourceExistsError
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
