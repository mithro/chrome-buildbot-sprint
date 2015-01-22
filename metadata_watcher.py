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

def compare(old, new, handler, name=""):
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

    >>> # Test lists
    >>> l = {'a': [1, 2, 3]}
    >>> compare(l, l, onchange)
    >>> compare(l, {'a': []}, onchange)
    a: [1, 2, 3] -> []
    a[]: 1 -> None
    a[]: 2 -> None
    a[]: 3 -> None
    >>> compare({'a': []}, l, onchange)
    a: [] -> [1, 2, 3]
    a[]: None -> 1
    a[]: None -> 2
    a[]: None -> 3
    >>> l_add = deepcopy(l)
    >>> l_add['a'].append(4)
    >>> compare(l, l_add, onchange)
    a: [1, 2, 3] -> [1, 2, 3, 4]
    a[]: None -> 4
    >>> l_remove = deepcopy(l)
    >>> l_remove['a'].pop(0)
    1
    >>> compare(l, l_remove, onchange)
    a: [1, 2, 3] -> [2, 3]
    a[]: 1 -> None
    >>> l_remove['a'].pop(-1)
    3
    >>> compare(l, l_remove, onchange)
    a: [1, 2, 3] -> [2]
    a[]: 1 -> None
    a[]: 3 -> None
    >>>

    >>> # Test dicts inside lists
    >>> l = {'a': [{'b':1}, {'c': 2}]}
    >>> compare(l, l, onchange)
    >>> compare(l, {'a': []}, onchange)
    a: [{'b': 1}, {'c': 2}] -> []
    a[]: {'b': 1} -> None
    a[].b: 1 -> None
    a[]: {'c': 2} -> None
    a[].c: 2 -> None
    >>> compare({'a': []}, l, onchange)
    a: [] -> [{'b': 1}, {'c': 2}]
    a[]: None -> {'b': 1}
    a[].b: None -> 1
    a[]: None -> {'c': 2}
    a[].c: None -> 2
    >>> l_add = deepcopy(l)
    >>> l_add['a'].append({'d': 3})
    >>> compare(l, l_add, onchange)
    a: [{'b': 1}, {'c': 2}] -> [{'b': 1}, {'c': 2}, {'d': 3}]
    a[]: None -> {'d': 3}
    a[].d: None -> 3
    >>> l_add = deepcopy(l)
    >>> l_add['a'][0]['d'] = 3
    >>> compare(l, l_add, onchange)
    a: [{'b': 1}, {'c': 2}] -> [{'b': 1, 'd': 3}, {'c': 2}]
    a[]: None -> {'b': 1, 'd': 3}
    a[].b: None -> 1
    a[].d: None -> 3
    a[]: {'b': 1} -> None
    a[].b: 1 -> None
    >>> l_remove = deepcopy(l)
    >>> l_remove['a'].pop(0)
    {'b': 1}
    >>> compare(l, l_remove, onchange)
    a: [{'b': 1}, {'c': 2}] -> [{'c': 2}]
    a[]: {'b': 1} -> None
    a[].b: 1 -> None
    >>>
    """
    if old == new:
        return

    if name:
        handler(name, old, new)

    if isinstance(old, dict) or isinstance(new, dict):
        if not isinstance(old, dict):
            dold = {}
        else:
            dold = old

        if not isinstance(new, dict):
            dnew = {}
        else:
            dnew = new

        old_keys = set(dold.keys())
        new_keys = set(dnew.keys())
        for key in sorted(old_keys.union(new_keys)):
            if name:
                childname = ("%s.%s" % (name, key))
            else:
                childname = key

            old_value = dold.get(key, None)
            new_value = dnew.get(key, None)
            compare(old_value, new_value, handler, childname)

    if isinstance(old, (list, tuple)) or isinstance(new, (list, tuple)):
        if not isinstance(old, (list, tuple)):
            lold = []
        else:
            lold = old
        if not isinstance(new, (list, tuple)):
            lnew = []
        else:
            lnew = new

        """
        >>> # Test dicts inside lists
        >>> l = {'a': [{'b':1}, {'c': 2}]}
        >>> compare(l, l, onchange)
        >>> compare(l, {'a': []}, onchange)
        a: [{'b': 1}, {'c': 2}] -> []
        a[]: {'b': 1} -> None
        a[].b: 1 -> None
        a[]: {'c': 2} -> None
        a[].c: 2 -> None
        >>> compare({'a': []}, l, onchange)
        a: [] -> [{'b': 1}, {'c': 2}]
        a[]: None -> {'b': 1}
        a[].b: None -> 1
        a[]: None -> {'c': 2}
        a[].c: None -> 2
        >>> l_add = deepcopy(l)
        >>> l_add['a'].append({'d': 3})
        >>> compare(l, l_add, onchange)
        a: [{'b': 1}, {'c': 2}] -> [{'b': 1}, {'c': 2}, {'d': 3}]
        a[]: None -> {'d': 3}
        a[].d: None -> 3
        >>> l_add = deepcopy(l)
        >>> l_add['a'][0]['d'] = 3
        >>> compare(l, l_add, onchange)
        a: [{'b': 1}, {'c': 2}] -> [{'b': 1, 'd': 3}, {'c': 2}]
        a[]: {'b': 1} -> {'b': 1, 'd': 3}
        a[].d: None -> 3
        >>> l_remove = deepcopy(l)
        >>> l_remove['a'].pop(0)
        {'b': 1}
        >>> compare(l, l_remove, onchange)
        a: [{'b': 1}, {'c': 2}] -> [{'c': 2}]
        a[]: {'b': 1} -> {}
        a[].b: 1 -> None
        >>>
        values = lnew + lold
        if isinstance(values[0], dict):
            for i in range(0, max(len(lold), len(lnew))):
                if i < len(lold):
                    old_value = lold[i]
                else:
                    old_value = None

                if i < len(lnew):
                    new_value = lnew[i]
                else:
                    new_value = None

                compare(old_value, new_value, handler, name+"[]")
            return
        """

        values = lnew + lold
        for v in values:
            if v in lold:
                old_value = v
            else:
                old_value = None

            if v in lnew:
                new_value = v
            else:
                new_value = None

            compare(old_value, new_value, handler, name + "[]")


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


    >>> m = MetadataHandler()
    >>> m.update(old)
    >>> m.get('a')
    1
    >>> m.get('c')
    {'e': 4, 'd': 3}
    >>> # Can't modify returned data
    >>> m.get('c')['d'] = 5
    >>> m.get('c')
    {'e': 4, 'd': 3}
    >>> m.get('c.d')
    3
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

    _sentinal = []
    def get(self, key, default=_sentinal):
        with self.lock:
            fullkey = key

            current = self.data
            while True:
                if key in current or '.' not in key:
                    if key in current:
                        return copy.deepcopy(current[key])
                    elif default is not self._sentinal:
                        return default
                    else:
                        raise KeyError("%s not found" % fullkey)

                if '.' in key:
                    p, key = key.split('.', 1)
                    if p not in current:
                        if default is not self._sentinal:
                            return default
                        else:
                            raise KeyError("%s not found" % fullkey)
                    current = current[p]

    __getitem__ = get


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

    def get(self, key):
        self.metadata.get(key)

    def run(self):
        while True:
            params = dict(self.params)
            params['last_etag'] = self.last_etag
            url = '{base_url}?{params}'.format(
                base_url=METADATA_URL,
                params=urllib.urlencode(params)
                )

            print "Fetching %r" % url
            req = urllib2.Request(url, headers={'Metadata-Flavor': 'Google'})

            try:
                response = urllib2.urlopen(req)
                content = response.read()
                status = response.getcode()
                print "Got response %s" % status
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


import socket
import platform
import pprint

class Server(object):
    CALLBACK_URL="project.attributes.callback"

    def __init__(self, metadata_watcher):
        self.metadata = metadata_watcher

    def post_action(self, data):
        assert self.metadata.get(self.CALLBACK_URL), """\
Please add the callback URL for status information to the Compute Engine project with;
# gcloud compute project-info add-metadata --metadata callback="http://example.com/callback"
"""

        extra_data = {
            "hostname": socket.gethostname(),
            "node": platform.node(),
            "env": copy.deepcopy(os.environ),
            }
        full_data = copy.deepcopy(data)
        full_data.update(extra_data)

        # Post data here
        pprint.pprint((
            self.metadata[self.CALLBACK_URL],
            full_data))


import subprocess

class Handler(object):
    def __init__(self, server, metadata_watcher):
        assert self.NAMESPACE, "%s must set NAMESPACE class attribute" % (self.__class__)
        self.server = server
        self.metadata = metadata_watcher
        self.metadata.add_handler(self.NAMESPACE, self)

    def __call__(self, name, old_value, new_value):
        assert re.match(MATCH, name)
        success = False
        output = ""
        try:
            if old_value is None:
                success, output = self.add(new_value)
            elif new_value is None:
                success, output = self.remove(old_value)
            elif new_value != old_value:
                success, output = self.change(old_value, new_value)
            else:
                assert False
        except Exception, e:
            success = "Exception"
            output += str(e)
            # Include traceback
        finally:
            self.server.post_action({
                "success": success,
                "output": output,
                "hostname": socket.gethostname(),
                })

    @staticmethod
    def run_helper(cmd, output):
        output.append("="*80)
        output.append("Running: %r" % cmd)
        output.append("----")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = p.communicate()
        retcode = p.wait()
        output.append(stdout)
        output.append("----")
        output.append("Completed with: %s" % retcode)
        output.append("="*80)
        return retcode

    NAMESPACE = None
    def add(self, value):
        pass

    def remove(self, value):
        pass

    def change(self, old_value, new_value):
        pass


import os.path
class HandlerMount(Handler):
    NAMESPACE = "instance.attributes.disks$"

    @staticmethod
    def device(disk_id):
        return "/dev/disk/by-id/google-%s" % disk_id

    def assert_disk_attached(self, disk_id):
        for attached_disk in self.metadata['instance.disks']:
            if attached_disk['deviceName'] == disk_id:
                break
        else:
            raise Exception("Disk with id %r not found on instance %r" % (
                disk_id, self.metadata.data['instance.disks']))

    def add(self, value):
        assert 'mount-point' in value
        assert 'disk-id' in value
        self.assert_disk_attached(value['disk_id'])

        output = []
        success = True

        # Make the mount point directory if it doesn't exist
        if not os.path.exists(value['mount-point']):
            os.makedirs(value['mount-point'])

        # Mount the directory
        success &= 0 == self.run_helper("""\
mount %s %s
""" % (self.device(value['disk-id']), value['mount-point']), output)

        # Chown the directory if needed
        if 'user' in value:
            success &= 0 == self.run_helper("chown %s" % value['user'], output)

        return success, output

    def remove(self, value):
        assert 'mount-point' in value
        assert 'disk-id' in value
        self.assert_disk_attached(value['disk_id'])

        output = []
        success = True

        prefix = self.device(value['disk_id']) + " "
        for line in open('/proc/mounts', 'r').readlines():
            if line.startswith(prefix):
                assert line.startswith(prefix+value['mount-point'])
                success &= 0 == self.run_helper("umount %s" % value['mount-point'])

        return success, output


class HandlerShutdown(Handler):
    NAMESPACE = "instance.attributes.shutdown"

    def add(self, value):
        assert value == 1
        output = []
        return 0 == self.run_helper("shutdown -h +1", output), output

    def remove(self, value):
        return 0 == self.run_helper("shutdown -c", output), output


class HandlerCommand(Handler):
    NAMESPACE = "instance.attributes.commands[]"

    def add(self, value):
        output = []
        return 0 == self.run_helper(value, output), output


def Printer(name, old_value, new_value):
    if isinstance(old_value, (dict, list)) or isinstance(new_value, (dict, list)):
        return

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
    server = Server(watcher)
    HandlerMount(server, watcher)
    HandlerCommand(server, watcher)
    HandlerShutdown(server, watcher)

    watcher.add_handler(".*", Printer)
    watcher.start()
    watcher.join()




