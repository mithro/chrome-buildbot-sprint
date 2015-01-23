# import libcloud_gae
import webapp2

# HACK: Using memcache as a temp DB
from google.appengine.api import memcache


class CallbackHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Last callback: ' + memcache.get('last_callback'))

  def post(self):
    memcache.set('last_callback', self.request.get('data'))
    # instance_name = self.request.get('instance_name')
    # key = self.request.get('key')
    # value = self.request.get('value')
    # driver = libcloud_gae.new_driver()
    # node = driver.ex_get_node(instance_name)
    # driver.ex_set_node_metadata(node, {
    #   'items': node.extra['metadata']['items'] + [{'key': key, 'value': value}],
    # })

    # self.response.write('Added %s: %s to %s' % (key, value, instance_name))


APP = webapp2.WSGIApplication([
  ('/callback/?', CallbackHandler),
], debug=True)
