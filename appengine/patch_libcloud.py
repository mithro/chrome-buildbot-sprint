
import types

# Needed because libcloud uses os.expanduser
import os
os.environ['HOME'] = '/FAKE_HOME'

# The google library tries to write a file containing an auth token to a local
# file. Map it to memory instead.
from libcloud.common.google import GoogleBaseConnection
TOKEN=None
def get_token(self):
  print "TOKEN read as: %r" % TOKEN
  return TOKEN

def set_token(self):
  global TOKEN
  print self
  print "TOKEN set to: %r" % self.token_info
  TOKEN = self.token_info

GoogleBaseConnection._get_token_info_from_file = get_token #, GoogleBaseConnection)
GoogleBaseConnection._write_token_info_to_file = set_token #, GoogleBaseConnection)
print GoogleBaseConnection._get_token_info_from_file
print GoogleBaseConnection._write_token_info_to_file
