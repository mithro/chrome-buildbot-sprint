#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

import httplib
import sys
import time
import urllib
import urllib2

METADATA_URL = 'http://metadata.google.internal/computeMetadata/v1/'

import copy
import re

def compare(old, new, parent="", handlers={}):
    """
    >>> from copy import deepcopy
    >>> def onchange(*args): print "%s: %r -> %r" % args
    >>> old_1 = {'a': 1, 'b': 2, 'c': {'d': 3, 'e': 4}}

    >>> # Same dictionary does nothing
    >>> same_1 = deepcopy(old_1)
    >>> compare(old_1, same_1, handlers={".*":[onchange]})

    >>> # Adding new field
    >>> new_1  = deepcopy(old_1)
    >>> new_1['f'] = 5
    >>> compare(old_1, new_1, handlers={".*":[onchange]})
    f: None -> 5
    >>> compare(old_1, new_1, handlers={"f":[onchange]})
    f: None -> 5
    >>> compare(old_1, new_1, handlers={"a":[onchange]})
    >>>

    >>> # Removing a field
    >>> del_1  = deepcopy(old_1)
    >>> del del_1['a']
    >>> compare(old_1, del_1, handlers={".*":[onchange]})
    a: 1 -> None
    >>> compare(old_1, del_1, handlers={"a":[onchange]})
    a: 1 -> None
    >>> compare(old_1, del_1, handlers={"f":[onchange]})
    >>>

    >>> # Nested compare
    >>> new_1  = deepcopy(old_1)
    >>> new_1['c']['f'] = 5
    >>> compare(old_1, new_1, handlers={".*":[onchange]})
    c: {'e': 4, 'd': 3} -> {'e': 4, 'd': 3, 'f': 5}
    c.f: None -> 5
    >>> compare(old_1, new_1, handlers={"c":[onchange]})
    c: {'e': 4, 'd': 3} -> {'e': 4, 'd': 3, 'f': 5}
    >>> compare(old_1, new_1, handlers={"c\\..*":[onchange]})
    c.f: None -> 5
    >>> compare(old_1, new_1, handlers={"a":[onchange]})
    >>> 
    >>> del_1  = deepcopy(old_1)
    >>> del del_1['c']['d']
    >>> compare(old_1, del_1, handlers={".*":[onchange]})
    c: {'e': 4, 'd': 3} -> {'e': 4}
    c.d: 3 -> None
    >>> compare(old_1, del_1, handlers={"c":[onchange]})
    c: {'e': 4, 'd': 3} -> {'e': 4}
    >>> compare(old_1, del_1, handlers={"c\\..*":[onchange]})
    c.d: 3 -> None
    >>> compare(old_1, del_1, handlers={"a":[onchange]})
    >>> 
    """
    if old is None:
        old = {}
    if new is None:
        new = {}

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    for key in old_keys.union(new_keys):
        old_value = old.get(key, None)
        new_value = new.get(key, None)

        if old_value == new_value:
            continue

        fullname = "%s.%s" % (parent, key)
        sname = fullname[1:]
        for matcher in handlers:
            if not re.match("^%s$" % matcher, sname):
                continue
            for handler in handlers[matcher]:
                handler(sname, old_value, new_value)

        if isinstance(old_value, dict) or isinstance(new_value, dict):
            compare(old_value, new_value, fullname, handlers)


import threading
try:
    import simplejson
except ImportError:
    import json as simplejson

class MetadataWatcher(threading.Thread):
    """
    Get all the metadata from the server, blocking on until a change has occurred.
    """

    def run_handler(self, matcher, handler, d):
        for key, value in d.items():

            if re.match("^%s$" % matcher, key):
                handler(vkey, None, value)

            if isinstance(value, dict):
                self.run_handler(matcher, handler, value)

    def add_handler(self, matcher, function):
        with self.metadata_lock:
            # Run the handler on any existing data
            self.run_handler(matcher, function)

            # Add the handler to the list
            if matcher not in self._handlers:
                self._handlers[matcher] = []
            self._handlers[key].append(function)

    def __init__(self):
        self.params = {
            'recursive': 'true',
            'wait_for_change': 'true',
            }

        self.last_etag = 0

        self._metadata_lock = threading.Lock()
        self.metadata = {}

        self._handlers = {}

    def run(self):
        while True:
            params = dict(self.params)
            params['last_tag'] = self.last_etag

            url = '{base_url}?{params}'.format(
                base_url=METADATA_URL,
                params=urllib.urlencode(params)
                )
            req = urllib2.Request(url, headers={'Metadata-Flavor': 'Google'})

            try:
                response = urllib2.urlopen(req)
                content = response.read()
                status = response.getcode()
            except urllib2.HTTPError as e:
                content = None
                status = e.code

            if status == httplib.SERVICE_UNAVAILABLE:
                time.sleep(1)
                continue
            elif status == httplib.OK:
                new_metatdata = simplejson.loads(content)

                with self.metadata_lock:
                    compare(self.metadata, new_metadata)
                    self.metadata = new_metadata

                    headers = response.info()
                    params['last_etag'] = headers['ETag']

            else:
                raise UnexpectedStatusException(status)











class Error(Exception):
  pass

class UnexpectedStatusException(Error):
  pass

class UnexpectedMaintenanceEventException(Error):
  pass

def WatchMetadata(metadata_key, handler, initial_value=None):
  """Watches for a change in the value of metadata.

  Args:
    metadata_key: The key identifying which metadata to watch for changes.
    handler: A callable to call when the metadata value changes. Will be passed
      a single parameter, the new value of the metadata.
    initial_value: The expected initial value for the metadata. The handler will
      not be called on the initial metadata request unless the value differs
      from this.

  Raises:
    UnexpectedStatusException: If the http request is unsuccessful for an
      unexpected reason.
  """
  params = {
      'wait_for_change': 'true',
      'last_etag': 0,
      }

  while True:
    value = initial_value
    # start a hanging-GET request for maintenance change events.
    url = '{base_url}{key}?{params}'.format(
        base_url=METADATA_URL,
        key=metadata_key,
        params=urllib.urlencode(params)
        )
    req = urllib2.Request(url, headers={'Metadata-Flavor': 'Google'})

    try:
      response = urllib2.urlopen(req)
      content = response.read()
      status = response.getcode()
    except urllib2.HTTPError as e:
      content = None
      status = e.code

    if status == httplib.SERVICE_UNAVAILABLE:
      time.sleep(1)
      continue
    elif status == httplib.OK:
      # Extract new maintenance-event value and latest etag.
      new_value = content
      headers = response.info()
      params['last_etag'] = headers['ETag']
    else:
      raise UnexpectedStatusException(status)

    # If the maintenance value changed, call the appropriate handler.
    if value != new_value:
      value = new_value
      handler(value)

def HandleMaintenance(on_maintenance_start, on_maintenance_end):
  """Watches for and responds to maintenance-event status changes.

  Args:
    on_maintenance_start: a callable to call before host maintenance starts.
    on_maintenance_end: a callable to call after host maintenance ends.

  Raises:
    UnexpectedStatusException: If the http request is unsuccessful for an
      unexpected reason.
    UnexpectedMaintenanceEventException: If the maintenance-event value is
      not either NONE or MIGRATE_ON_HOST_MAINTENANCE.

  Note: Instances that are set to TERMINATE_ON_HOST_MAINTENANCE will receive
  a power-button push and will not be notified through this script.
  """
  maintenance_key = 'instance/maintenance-event'

  def Handler(event):
    if event == 'MIGRATE_ON_HOST_MAINTENANCE':
      on_maintenance_start()
    elif event == 'NONE':
      on_maintenance_end()
    else:
      raise UnexpectedMaintenanceEventException(event)

  WatchMetadata(maintenance_key, Handler, initial_value='NONE')

def OnMaintenanceStart():
  # Add commands to perform before maintenance starts here.
  pass

def OnMaintenanceEnd():
  # Add commands to perform after maintenance is complete here.
  pass


if __name__ == "__main__":
    import doctest
    doctest.testmod()

"""
if __name__ == '__main__':
  # Perform actions when maintenance events occur.
  HandleMaintenance(OnMaintenanceStart, OnMaintenanceEnd)

  # An example of watching for changes in a different metadata field.
  # Replace 'foo' with an existing custom metadata key of your choice.
  #
  # WatchMetadata('instance/attributes/foo',
  #               lambda val: sys.stdout.write('%s\n' % val))
"""
