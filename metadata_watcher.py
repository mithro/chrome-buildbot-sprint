#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

import httplib
import sys
import time
import urllib
import urllib2

import signal

METADATA_URL = 'http://metadata.google.internal/computeMetadata/v1/'

import copy
import re

def compare(old, new, handler, parent=""):
    """
    >>> from copy import deepcopy
    >>> def onchange(*args): print "%s: %r -> %r" % args
    >>> old = {'a': 1, 'b': 2, 'c': {'d': 3, 'e': 4}}

    >>> # Same dictionary does nothing
    >>> same = deepcopy(old)
    >>> compare(old, same, onchange)

    >>> # Adding new field
    >>> new  = deepcopy(old)
    >>> new['f'] = 5
    >>> compare(old, new, onchange)
    f: None -> 5
    >>>

    >>> # Removing a field
    >>> remove  = deepcopy(old)
    >>> del remove['a']
    >>> compare(old, remove, onchange)
    a: 1 -> None
    >>>

    >>> # Nested compare
    >>> new  = deepcopy(old)
    >>> new['c']['f'] = 5
    >>> compare(old, new, onchange)
    c: {'e': 4, 'd': 3} -> {'e': 4, 'd': 3, 'f': 5}
    c.f: None -> 5
    >>> 
    >>> remove  = deepcopy(old)
    >>> del remove['c']['d']
    >>> compare(old, remove, onchange)
    c: {'e': 4, 'd': 3} -> {'e': 4}
    c.d: 3 -> None
    >>> 
    """
    if old is None:
        old = {}
    if new is None:
        new = {}

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    for key in sorted(old_keys.union(new_keys)):
        old_value = old.get(key, None)
        new_value = new.get(key, None)

        if old_value == new_value:
            continue

        fullname = "%s.%s" % (parent, key)
        sname = fullname[1:]
        handler(sname, old_value, new_value)

        if isinstance(old_value, dict) or isinstance(new_value, dict):
            compare(old_value, new_value, handler, fullname)


class Handlers(dict):
    """
    >>> from copy import deepcopy
    >>> def onchange(*args): print "%s: %r -> %r" % args
    >>> handle_all = Handlers({".*":[onchange]})
    >>> handle_a = Handlers({"a":[onchange]})
    >>> handle_c = Handlers({"c":[onchange]})
    >>> handle_c_child = Handlers({"c\\..*":[onchange]})
    >>> handle_f = Handlers({"f":[onchange]})
    >>> old = {'a': 1, 'b': 2, 'c': {'d': 3, 'e': 4}}
    >>> 
    >>> # Same dictionary does nothing
    >>> same = deepcopy(old)
    >>> compare(old, same, handle_all)
    >>> 

    >>> # Adding new field
    >>> new  = deepcopy(old)
    >>> new['f'] = 5
    >>> compare(old, new, handle_all)
    f: None -> 5
    >>> # Only handlers dealing with f should be triggered
    >>> compare(old, new, handle_a)
    >>> compare(old, new, handle_c)
    >>> compare(old, new, handle_c_child)
    >>> compare(old, new, handle_f)
    f: None -> 5
    >>> 

    >>> # Value changed
    >>> change  = deepcopy(old)
    >>> change['a'] = 2
    >>> compare(old, change, handle_all)
    a: 1 -> 2
    >>> # Only handlers dealing with a should be triggered
    >>> compare(old, change, handle_a)
    a: 1 -> 2
    >>> compare(old, change, handle_c)
    >>> compare(old, change, handle_c_child)
    >>> compare(old, change, handle_f)
    >>> 

    >>> # Removing a field
    >>> remove  = deepcopy(old)
    >>> del remove['a']
    >>> compare(old, remove, handle_all)
    a: 1 -> None
    >>> # Only handlers dealing with a should be triggered
    >>> compare(old, remove, handle_a)
    a: 1 -> None
    >>> compare(old, remove, handle_c)
    >>> compare(old, remove, handle_c_child)
    >>> compare(old, remove, handle_f)
    >>> 

    >>> # Nested compare adding
    >>> new  = deepcopy(old)
    >>> new['c']['f'] = 5
    >>> new['c']['g'] = 6
    >>> compare(old, new, handle_all)
    c: {'e': 4, 'd': 3} -> {'e': 4, 'd': 3, 'g': 6, 'f': 5}
    c.f: None -> 5
    c.g: None -> 6
    >>> compare(old, new, handle_a)
    >>> compare(old, new, handle_c)
    c: {'e': 4, 'd': 3} -> {'e': 4, 'd': 3, 'g': 6, 'f': 5}
    >>> compare(old, new, handle_c_child)
    c.f: None -> 5
    c.g: None -> 6
    >>> compare(old, new, handle_f)
    >>> 
    >>> # Nested compare removal
    >>> change  = deepcopy(old)
    >>> del change['c']['d']
    >>> compare(old, change, handle_all)
    c: {'e': 4, 'd': 3} -> {'e': 4}
    c.d: 3 -> None
    >>> compare(old, change, handle_a)
    >>> compare(old, change, handle_c)
    c: {'e': 4, 'd': 3} -> {'e': 4}
    >>> compare(old, change, handle_c_child)
    c.d: 3 -> None
    >>> compare(old, change, handle_f)
    >>> 
    >>> # Nested compare removal
    >>> remove  = deepcopy(old)
    >>> del remove['c']['d']
    >>> compare(old, remove, handle_all)
    c: {'e': 4, 'd': 3} -> {'e': 4}
    c.d: 3 -> None
    >>> compare(old, remove, handle_a)
    >>> compare(old, remove, handle_c)
    c: {'e': 4, 'd': 3} -> {'e': 4}
    >>> compare(old, remove, handle_c_child)
    c.d: 3 -> None
    >>> compare(old, remove, handle_f)
    >>> 
    """

    def __call__(self, name, old_value, new_value):
        for matcher in self:
            if not re.match("^%s$" % matcher, name):
                continue

            for handler in self[matcher]:
                handler(name, old_value, new_value)

    def add(self, matcher, handler):
        if matcher not in self:
            self[matcher] = []
        self[matcher].append(handler)


class MetadataHandler(object):
    """
    >>> from copy import deepcopy
    >>> def onchange(*args): print "%s: %r -> %r" % args
    >>> 
    >>> old = {'a': 1, 'b': 2, 'c': {'d': 3, 'e': 4}}
    >>> m = MetadataHandler()
    >>> 
    >>> # Update the values should call handler
    >>> m.add_handler("a", onchange)
    >>> m.update(old)
    a: None -> 1
    >>> 
    >>> # Adding a new handler calls it if the data already exists
    >>> m.add_handler("b", onchange)
    b: None -> 2
    >>> 
    >>> # Update with same values shouldn't call anything
    >>> m.update(old)
    >>> 
    >>> # Updated values
    >>> m.add_handler("f", onchange)
    >>> change  = deepcopy(old)
    >>> del change['a'] # Remove
    >>> change['b'] = 3 # Change
    >>> change['f'] = 5 # Add
    >>> m.update(change)
    a: 1 -> None
    b: 2 -> 3
    f: None -> 5
    >>> 
    """

    def __init__(self):
        self.handlers = Handlers()
        self.data = {}

        self.lock = threading.RLock()

    def update(self, new_data):
        with self.lock:
            compare(self.data, new_data, self.handlers)
            self.data = new_data

    def add_handler(self, matcher, function):
        with self.lock:
            # Call the handler with the current data value
            temp_handlers = Handlers()
            temp_handlers.add(matcher, function)
            compare({}, self.data, temp_handlers)

            # Add the handler
            self.handlers.add(matcher, function)

    def __getitem__(self, key):
        return self.data[key]

    def __getattr__(self, key):
        return self.data[key]


import threading
try:
    import simplejson
except ImportError:
    import json as simplejson


class Error(Exception):
  pass


class UnexpectedStatusException(Error):
  pass


class MetadataWatcher(threading.Thread):
    """
    Get all the metadata from the server, blocking on until a change has occurred.
    """

    def __init__(self, params={}):
        threading.Thread.__init__(self)

        self.params = {
            'recursive': 'true',
            'wait_for_change': 'true',
            }
        self.params.update(params)

        self.last_etag = 0
        self.metadata = MetadataHandler()

    def add_handler(self, matcher, function):
        self.metadata.add_handler(matcher, function)

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
                new_metadata = simplejson.loads(content)
                self.metadata.update(new_metadata)
                headers = response.info()
                self.last_etag = headers['ETag']
            else:
                raise UnexpectedStatusException(status)


def HandlerPrinter(name, old_value, new_value):
    if old_value is None:
        print "  Added: %s(%r)" % (name, new_value)
        return
    if new_value is None:
        print "Removed: %s(was %r)" % (name, old_value)
        return
    else:
        print "Changed: %s(%r -> %r)" % (name, old_value, new_value)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    watcher = MetadataWatcher()
    watcher.add_handler(".*", HandlerPrinter)
    watcher.start()
    watcher.join()
