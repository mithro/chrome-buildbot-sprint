
from google.appengine.ext import db


class TestResults(db.Model):
  """|key_name| is the test run id."""
  xml_data = db.StringProperty()
  timestamp = db.DateTimeProperty()
