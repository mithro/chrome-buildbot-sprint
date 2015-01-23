#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

import cStringIO as StringIO
import copy
import httplib
import os.path
import platform
import pprint
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib
import urllib2

import tempfile
outputfile = open(tempfile.mktemp(prefix="metadata_watcher.%s." % os.getpid(), suffix=".log"), 'w+', 100)
sys.stdout.close()
sys.stdout = outputfile
sys.stderr.close()
sys.stderr = outputfile
sys.stdin.close()

try:
    import simplejson
except ImportError:
    import json as simplejson

from multiprocessing.pool import ThreadPool

METADATA_URL = 'http://metadata.google.internal/computeMetadata/v1/'


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
    # FIXME: HACKS!?@
    if isinstance(old, (str, unicode)):
        if old and old[0] in ('[', '{'):
            try:
                old = simplejson.loads(old)
            except Exception, e:
		print name, "JSON Error->:", old
		pass
    if isinstance(new, (str, unicode)):
        if new and new[0] in ('[', '{'):
            try:
                new = simplejson.loads(new)
            except Exception, e:
		print name, "JSON Error->:", new
		pass

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
        self._data = {}

        self.lock = threading.RLock()

    def update(self, new_data):
        with self.lock:
            compare(self._data, new_data, self.handlers)
            self._data = new_data

    def add_handler(self, matcher, function):
        with self.lock:
            # Call the handler with the current data value
            temp_handlers = Handlers()
            temp_handlers.add(matcher, function)
            compare({}, self._data, temp_handlers)

            # Add the handler
            self.handlers.add(matcher, function)

    _sentinal = []
    def get(self, key, default=_sentinal):
        with self.lock:
            if key is None:
                return copy.deepcopy(self._data)

            fullkey = key

            current = self._data
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

        # Fetch the project metadata once first
        _, new_metadata = self.fetch()
        self.metadata.update(new_metadata)

    def add_handler(self, matcher, function):
        self.metadata.add_handler(matcher, function)

    def get(self, key, default=MetadataHandler._sentinal):
        return self.metadata.get(key, default)

    __getitem__ = get

    def fetch(self):
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
                headers = response.info()
                new_metadata = simplejson.loads(content)
                return headers['ETag'], new_metadata
            else:
                raise UnexpectedStatusException(status)

    def run(self):
        while True:
            etag, new_metadata = self.fetch()
            self.metadata.update(new_metadata)
            self.last_etag = etag

class Server(object):
    CALLBACK_URL="project.attributes.callback"

    def __init__(self, metadata_watcher):
        self.metadata = metadata_watcher

    def post_action(self, data):
        assert self.metadata.get(self.CALLBACK_URL), """\
Please add the callback URL for status information to the Compute Engine project with;
# gcloud compute project-info add-metadata --metadata callback="http://example.com/callback"
Current project metadata:
%s
""" % (pprint.pformat(self.metadata.get("project", None)))

        extra_data = {
            "hostname": socket.gethostname(),
            "node": platform.node(),
            "env": dict(os.environ),
            }
        full_data = copy.deepcopy(data)
        full_data.update(extra_data)

        # Post data here
        print "=+"*30
        url = self.metadata[self.CALLBACK_URL]
        print "Posting data to %s" % url
        output = full_data["output"]
        del full_data["output"]
        try:
            for k, v in full_data.items():
                print 'JSONIZING %s, %r' % (k, v)
                simplejson.dumps(v)
            print 'Post response from %s: %s' % (url, urllib2.urlopen(url, data=urllib.urlencode({'data': simplejson.dumps(full_data)})).read())
        except Exception as e:
            print 'ERROR:', e
        pprint.pprint((url, full_data))
        print "-"*80
        print output
        print "=+"*30


class Handler(object):
    def __init__(self, server, metadata_watcher):
        assert self.NAMESPACE, "%s must set NAMESPACE class attribute" % (self.__class__)
        self.server = server
        self.metadata = metadata_watcher
        self.metadata.add_handler(self.NAMESPACE, self)

    def __call__(self, name, old_value, new_value, **kw):
        success = False
        output = []
        func = None
        try:
            if old_value is None:
                if not hasattr(self, 'add'):
                    return
                func = self.add
                success, output = self.add(name, new_value, **kw)
            elif new_value is None:
                if not hasattr(self, 'remove'):
                    return
                func = self.remove
                success, output = self.remove(name, old_value, **kw)
            elif new_value != old_value:
                if hasattr(self, 'change'):
                    return
                func = self.change
                success, output = self.change(name, old_value, new_value, **kw)
            else:
                assert False
        except Exception, e:
            success = "Exception"
            output.append(str(e))
            tb = StringIO.StringIO()
            traceback.print_exc(file=tb)
            tb.seek(0)
            output.append(tb.getvalue())
        finally:
            data = {
                "type": "finished",
                "function": "%r" % func,
                "success": success,
                "output": "\n".join(output),
                }
            if new_value and 'output-file' in new_value:
                open(new_value['output-file'], 'w').write(simplejson.dumps(data))
            self.post(data)

    def post(self, data):
        data.update({
            "handler": self.__class__.__name__,
        })
        self.server.post_action(data)

    @classmethod
    def run_helper(cls, cmd, output):
        output.append("="*80)
        output.append("Running: %r" % cmd)
        output.append("----")
        outfile = tempfile.NamedTemporaryFile(prefix="%s." % (cls.__name__))
        print "Running %r and writing log to %r" % (cmd, outfile.name)
        p = subprocess.Popen(cmd, stdout=outfile, stderr=subprocess.STDOUT, shell=True)
        retcode = p.wait()
        outfile.seek(0)
        output.append(outfile.read())
        output.append("----")
        output.append("Completed with: %s" % retcode)
        output.append("="*80)
        return retcode

    NAMESPACE = None
    """
    def add(self, name, value):
        pass

    def remove(self, name, value):
        pass

    def change(self, name, old_value, new_value):
        pass
    """

class HandlerAsync(Handler):
    WORKERS=10

    @property
    def metadata(self):
        if threading.currentThread() != self.thread:
            raise SystemError("Can't access metadata when async.")
        else:
            return self.__metadata

    @metadata.setter
    def metadata(self, value):
        self.__metadata = value

    def __init__(self, *args, **kw):
        self.pool = ThreadPool(self.WORKERS)
        self.thread = threading.currentThread()
        Handler.__init__(self, *args, **kw)

    def __call__(self, *args, **kw):
        kw['metadata'] = copy.deepcopy(self.__metadata.get(None))
        self.pool.apply_async(Handler.__call__, [self]+list(args), kw)

    """
    def add(self, name, value, metadata=None):
        pass

    def remove(self, name, value, metadata=None):
        pass

    def change(self, name, old_value, new_value, metadata=None):
        pass
    """

class HandlerLongCommand(HandlerAsync):
    NAMESPACE = r"instance\.attributes\.long-commands\[\]"
    def add(self, name, value, metadata=None):
        assert metadata is not None
        assert 'cmd' in value
        if isinstance(value['cmd'], unicode):
            value['cmd'] = value['cmd'].encode('utf-8')
        if 'user' in value:
            cmd = "su %s -c %r" % (value['user'], value['cmd'])
        else:
            cmd = value['cmd']
        output = []
        output.append("="*80)
        output.append("Running: %r" % cmd)
        output.append("----")
        outfile = tempfile.NamedTemporaryFile(prefix="%s." % (self.__class__.__name__))
        print "Running %r and writing log to %r" % (cmd, outfile.name)
        p = subprocess.Popen(cmd, stdout=outfile, stderr=subprocess.STDOUT, shell=True)

        while True:
            self.post({
                "type": "progress",
                "cmd" : cmd,
                "output": open(outfile.name, 'r').read(),
            })

            retcode = p.poll()
            if retcode is not None:
                break
            else:
                time.sleep(5)

        outfile.seek(0)
        output.append(outfile.read())
        output.append("----")
        output.append("Completed with: %s" % retcode)
        output.append("="*80)
        return retcode == 0, output


class HandlerEnvironment(Handler):
    QUIET=True
    NAMESPACE = r"(instance\.attributes\.env\..*)|(project\.attributes\.env\..*)"

    @staticmethod
    def trim_name(name):
        """
        >>> HandlerEnvironment.trim_name("asdasdasdsa.env.blah")
        'blah'
        >>> HandlerEnvironment.trim_name("a.env..env.")
        '.env.'
        """
        i = name.find(".env.")
        assert i != -1
        return name[i+5:]

    def __call__(self, name, old_value, new_value, **kw):
        name = self.trim_name(name)
        if new_value is None:
            del os.environ[name]
            return
        if not isinstance(new_value, str):
            new_value = str(new_value)
        if isinstance(new_value, unicode):
            new_value = new_value.encode('utf-8')
        os.environ[name] = new_value


class HandlerDiskBase(Handler):
    @staticmethod
    def device(disk_id):
        return "/dev/disk/by-id/google-%s" % disk_id

    def assert_disk_attached(self, disk_id):
        for attached_disk in self.metadata['instance.disks']:
            if attached_disk['deviceName'] == disk_id:
                break
        else:
            raise Exception("Disk with id %r not found on instance %r" % (
                disk_id, self.metadata['instance.disks']))

    def mount(self, _, value):
        assert 'mount-point' in value, value
        assert 'disk-id' in value, value
        self.assert_disk_attached(value['disk-id'])

        output = []
        success = True

        # Make the mount point directory if it doesn't exist
        if not os.path.exists(value['mount-point']):
            os.makedirs(value['mount-point'])

        # Mount the directory
        success &= (0 == self.run_helper("mount %s %s" % (
            self.device(value['disk-id']), value['mount-point']), output))

        # Chown the directory if needed
        if 'user' in value:
            success &= (0 == self.run_helper("chown %s %s" % (
                value['user'], value['mount-point']), output))

        success &= (0 == self.run_helper("ls -la %s" % (
            value['mount-point']), output))

        return success, output

    def umount(self, _, value):
        assert 'mount-point' in value
        assert 'disk-id' in value
        self.assert_disk_attached(value['disk-id'])

        output = []
        success = True
        found = False

        self.run_helper("cat /proc/mounts", output)

        prefix = os.path.realpath(self.device(value['disk-id'])) + " "
        for line in open('/proc/mounts', 'r').readlines():
            if line.startswith(prefix):
                assert line.startswith(prefix+value['mount-point'])
                found = True
                success &= (0 == self.run_helper("umount %s" % value['mount-point'], output))

        return (found and success), output


class HandlerMount(HandlerDiskBase):
    NAMESPACE = r"instance\.attributes\.mount\[\]"
    add = HandlerDiskBase.mount


class HandlerUnmount(HandlerDiskBase):
    NAMESPACE = r"instance\.attributes\.umount\[\]"
    add = HandlerDiskBase.umount


class HandlerShutdown(HandlerAsync):
    WORKERS = 2
    NAMESPACE = r"instance\.attributes\.shutdown"

    def add(self, name, value, metadata):
        output = []
        return 0 == self.run_helper("shutdown -h +1", output), output

    def remove(self, name, value, metadata):
        output = []
        return 0 == self.run_helper("shutdown -c", output), output


class HandlerCommand(Handler):
    NAMESPACE = r"instance\.attributes\.commands\[\]"

    def add(self, name, value):
        assert 'cmd' in value
        if isinstance(value['cmd'], unicode):
            value['cmd'] = value['cmd'].encode('utf-8')
        if 'user' in value:
            cmd = "su %s -c %r" % (value['user'], value['cmd'])
        else:
            cmd = value['cmd']

        output = []
        return 0 == self.run_helper(cmd, output), output


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
    HandlerEnvironment(server, watcher)
    HandlerMount(server, watcher)
    HandlerUnmount(server, watcher)
    HandlerCommand(server, watcher)
    HandlerLongCommand(server, watcher)
    HandlerShutdown(server, watcher)

    watcher.add_handler(".*", Printer)
    watcher.start()
    watcher.join()




