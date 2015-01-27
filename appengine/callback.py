import libcloud_gae
import logging
import webapp2
import json

from google.appengine.ext import ndb

from objects import Instance

# ---------------------------------------------------

import tasklets

TASKLET_TYPES = {}
for name in dir(tasklets):
  value = getattr(tasklets, name)
  if isinstance(value, type) and issubclass(value, tasklets.MetadataTasklet) and not value == tasklets.MetadataTasklet:
    TASKLET_TYPES[value.HANDLER] = value

# ---------------------------------------------------

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
    if data.get('type') != 'finished':
      self.response.write('IGNORED')
      return
    last_callback = LastCallback.query().get()
    last_callback.data = data
    last_callback.put()
    driver = libcloud_gae.new_driver()
    instance_name = data['instance-name']
    instance = Instance.load(instance_name, driver=driver)
    handler = data['handler']
    tasklet_type = TASKLET_TYPES.get(handler)
    if tasklet_type:
      tasklet_type.handle_callback(driver, instance, data['success'], data['old-value'], data['new-value'])
      result = 'OK'
      logging.info(result)
    else:
      result = 'MAYBE OK'
      logging.warn(result)
      logging.warn(instance_name)
      logging.warn(handler)
    self.response.write(result)


APP = webapp2.WSGIApplication([
  ('/callback/?', CallbackHandler),
], debug=True)
