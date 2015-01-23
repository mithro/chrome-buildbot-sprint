#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

import getpass

def NoDash(string):
  return string.replace('-', '_')

def SnapshotName(commit, content):
  return '-'.join([NoDash(getpass.getuser()), 'snapshot', 'linux', NoDash(commit), content])

import sys
sys.path.append("third_party/python-dateutil-1.5")
import calendar
import dateutil.parser
def parse_time(timestamp_str):
  dt = dateutil.parser.parse(timestamp_str)
  return calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond

