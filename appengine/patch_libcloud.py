
import types

# Needed because libcloud uses os.expanduser
import os
os.environ['HOME'] = '/FAKE_HOME'

# The google library tries to write a file containing an auth token to a local
# file. Map it to memory instead.
from libcloud.common.google import GoogleBaseConnection
TOKEN=None
def get_token(self):
  return TOKEN

def set_token(self):
  global TOKEN
  TOKEN = self.token_info

GoogleBaseConnection._get_token_info_from_file = get_token
GoogleBaseConnection._write_token_info_to_file = set_token

# Needed because appengine doesn't have any certificate files
import libcloud.security
libcloud.security.VERIFY_SSL_CERT = False
