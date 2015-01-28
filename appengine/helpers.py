#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import os

inf = float("inf")

import getpass

def NoDash(string):
  return string.replace('-', '')

def Namespace():
  vid = os.environ.get('CURRENT_VERSION_ID', None)
  if vid:
    if not os.environ['APPLICATION_ID'].startswith('dev'):
      return NoDash(vid)
    else:
      return open(os.path.join(os.path.dirname(__file__), 'whoami')).read().strip()
  return NoDash(os.environ['USER'])

def SnapshotName(commit, content):
  return '-'.join([Namespace(), 'linux', NoDash(commit), 'snapshot', content])

import sys
sys.path.append("third_party/python-dateutil-1.5")
import calendar
import dateutil.parser
def parse_time(timestamp_str):
  dt = dateutil.parser.parse(timestamp_str)
  return calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond

def special_update(current, key, value):
  """
  >>> a = {}
  >>> special_update(a, 'b.c', 1)
  >>> a
  {'b': {'c': 1}}
  >>>
  """
  while '.' in key:
      p, key = key.split('.', 1)
      if p not in current:
        current[p] = {}
      current = current[p]
  current[key] = value

if __name__ == "__main__":
    import doctest
    doctest.testmod()
