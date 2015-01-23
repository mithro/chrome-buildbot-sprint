import libcloud_gae
import webapp2
import json

from google.appengine.ext import ndb

class LastCallback(ndb.Model):
  data = ndb.JsonProperty(required=True)

class CallbackHandler(webapp2.RequestHandler):
  def get(self):
    assert 0 <= LastCallback.query().count() <= 1
    last_callback = LastCallback.query().get()
    self.response.write(json.dumps(last_callback.data))
    self.response.headers.add_header('Content-Type', 'text/plain')

  def post(self):
    data = json.loads(self.request.get('data'))
    last_callback = LastCallback.query().get()
    last_callback.data = data
    last_callback.put()
    if 'set-flag' not in data or 'instance-name' not in data:
      self.response.write('No work to do.')
      return
    flag = data['set-flag']
    driver = libcloud_gae.new_driver()
    node = driver.ex_get_node(data['instance-name'])
    new_metadata = {}
    for item in node.extra['metadata']['items']:
      new_metadata[item['key']] = item['value']
    new_metadata[flag] = 'true'
    driver.ex_set_node_metadata(node, new_metadata)
    self.response.write('Set metadata flag: %s' % flag)

APP = webapp2.WSGIApplication([
  ('/callback/?', CallbackHandler),
], debug=True)
