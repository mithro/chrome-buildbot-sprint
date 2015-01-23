import libcloud_gae
import webapp2
import time


class SetMetadataHandler(webapp2.RequestHandler):
  # FIXME: Use post instead
  def get(self):
    instance_name = self.request.get('instance_name')
    key = self.request.get('key')
    value = self.request.get('value')
    driver = libcloud_gae.new_driver()
    node = driver.ex_get_node(instance_name)
    driver.ex_set_node_metadata(node, {
      'items': node.extra['metadata']['items'] + [{'key': key, 'value': value}],
    })

    self.response.write('Added %s: %s to %s' % (key, value, instance_name))


APP = webapp2.WSGIApplication([
  ('/set_metadata/?', SetMetadataHandler),
], debug=True)
