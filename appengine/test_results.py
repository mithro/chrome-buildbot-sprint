#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

from google.appengine.ext import db
from db_objects import TestResults
import datetime
import webapp2
import time

PAGE_TEMPLATE = """\
<html>
  <head>
    <meta http-equiv="refresh" content="30">
    <title>{}</title>
  </head>
  <body>
  <h1>{}</h1>
  <tt>time: {}</tt><br><br>
  {}
  </body>
</html>
"""

PAGE_SUMMARY_TEMPLATE = """\
  <h1>Entries:</h1>
  <tt>{}</tt>
"""

PAGE_LINK_TEMPLATE = """\
  <a href="/test_results/{}">{}</a>
"""

PAGE_ENTRY_TEMPLATE = """\
  Entry timestamp: {}<br>
  Data:<br>
  <pre>{}</pre>
"""

POST_RESPONSE_TEMPLATE = """\
<html><body>
  <tt>time: {}</tt><br>
  <h1>{}</h1><br>
  Received:<br>
  <pre>{}</pre>
</body></html>)
"""


class TestResultsHandler(webapp2.RequestHandler):
  def post(self):
    start = time.time()

    path = self.request.path[len('/test_results/'):]
    data = self.request.arguments()[0]

    test_results = TestResults(key_name=path,
                               xml_data=data,
                               timestamp=datetime.datetime.utcnow())
    test_results.put()

    self.response.write(POST_RESPONSE_TEMPLATE.format(time.time() - start,
                                                      path,
                                                      data))

  def get(self):
    start = time.time()

    path = self.request.path[len('/test_results/'):]

    if path:
      test_results = TestResults.get_by_key_name(path)
      if test_results:
        result = PAGE_TEMPLATE.format(
          'test_results/' + path,
          'Test Results: ' + path,
          time.time() - start,
          PAGE_ENTRY_TEMPLATE.format(test_results.timestamp, test_results.xml_data),
        )
      else:
        result = PAGE_TEMPLATE.format(
          'test_results/' + path,
          'Test Results (not found): ' + path,
          time.time() - start,
          '',
        )
    else :
      query = TestResults.all(keys_only=True)
      query.order('-timestamp')
      test_result_keys = query.fetch(limit=100)
      result = PAGE_TEMPLATE.format(
        'test_results',
        'Test Results List',
        time.time() - start,
        PAGE_SUMMARY_TEMPLATE.format(
          '<br>\n'.join([PAGE_LINK_TEMPLATE.format(i.name(), i.name()) for i in test_result_keys])),
      )

    self.response.write(result)

