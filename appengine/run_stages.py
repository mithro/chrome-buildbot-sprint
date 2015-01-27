#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

try:
  from termcolor import cprint as print_color
except ImportError:
  def print_color(*args, **kw):
    print(*args, **kw)

import sys
def info(type, value, tb):
  from libcloud.common.google import ResourceInUseError
  if hasattr(sys, 'ps1') or not sys.stderr.isatty() or isinstance(type, ResourceInUseError):
    # we are in interactive mode or we don't have a tty-like
    # device, so we call the default hook
    sys.__excepthook__(type, value, tb)
  else:
    import traceback, pdb
    # we are NOT in interactive mode, print the exception...
    traceback.print_exception(type, value, tb)
    print
    # ...then start the debugger in post-mortem mode.
    pdb.pm()

sys.excepthook = info


PADDING=60
END=' | '
def pretty_print_status(t, skip_tid=False):
  tid = t.tid
  if skip_tid:
    tid = '--->'

  if not skip_tid:
    padding = ' '*(PADDING - len(tid))
    print(padding, end='')

    tid = t.tid.split('-')
    print('-'.join(tid[:5]), end='-')
    print_color('-'.join(tid[5:]), color='cyan', end=' ')
    print('   ', end=END)
  else:
    print(' '*PADDING, end='')
    print('\-> ', end=END)

  if t.is_startable():
    print_color("startable(true) ", color='green', end=END)
  else:
    print("startable(false)", end=END)

  if t.is_running():
    print_color("running(true) ", color='red', end=END)
  else:
    print("running(false)", end=END)

  if t.is_finished():
    print_color("finished(true) ", color='blue', end=END)
  else:
    print("finished(false)", end=END)

  print()
  if isinstance(t, WaitOnOtherTasks):
    pretty_print_status(t.task_to_run, skip_tid=True)
  else:
    print()


import threading
print_lock = threading.RLock()

previous_commit = "fa1651193bf94120"
current_commit = "32cbfaa6478f66b9"

import libcloud_gae
driver = libcloud_gae.new_driver()
starting_snap = Snapshot.load(SnapshotName(previous_commit, "src"), driver=driver)
assert starting_snap.exists(), starting_snap.name

import threading
import pprint
class Updater(threading.Thread):
  output = True
  ready = False
  go = True

  def skip(self, obj):
    return not obj.name.startswith(NoDash(getpass.getuser()) + '-new-')

  def run(self):
    driver = libcloud_gae.new_driver()
  
    old_nodes = []
    old_volumes = []
    old_snapshots = []
    while self.go:
      try:
        nodes = driver.list_nodes()
        volumes = driver.list_volumes()
        snapshots = driver.ex_list_snapshots()

        for node in nodes:
          if self.skip(node):
            continue
          Instance.load(node.name, gce_obj=node)

        for volume in volumes:
          if self.skip(volume):
            continue
          Disk.load(volume.name, gce_obj=volume)

        for snapshot in snapshots:
          if self.skip(snapshot):
            continue
          Snapshot.load(snapshot.name, gce_obj=snapshot)

        self.ready = True
        if self.output:
          if old_nodes != nodes or old_volumes != volumes or old_snapshots != snapshots:
            print("="*80+'\n', time.time(), "Finish updating gce\n", pprint.pformat(memcache), '\n'+"="*80+'\n')
          old_nodes = nodes
          old_volumes = volumes
          old_snapshots = snapshots
      except Exception, e:
        print(e)
        time.sleep(1)

updater = Updater()
updater.start()
while not updater.ready and updater.is_alive():
  time.sleep(1)

print("SyncStage")
print("-"*80)
for t in SyncStage(previous_commit, current_commit).tasklets():
  pretty_print_status(t)


try:
  updater.output = False
  raw_input("okay? ")
  updater.output = True

  """
  print("-"*80)
  print
  print("BuildStage")
  print("-"*80)
  for t in BuildStage(previous_commit, current_commit).tasklets():
    print(t)
    print(('startable', t.is_startable()), ('running', t.is_running()), ('done', t.is_finished()))
    print
  print("-"*80)
  """

  while updater.is_alive():
    print("-" * 80)
    for t in SyncStage(previous_commit, current_commit).tasklets():
      pretty_print_status(t)
      if t.is_startable():
        if t.is_running():
          continue

        if t.is_finished():
          continue

        updater.output = False
        raw_input("run (%s)? " % t.tid)
        updater.output = True
        def run(t=t):
          driver = libcloud_gae.new_driver()
          t.run(driver)
        threading.Thread(target=run).start()
    print("-" * 80)

    time.sleep(1)
finally:
  updater.go = False
    updater.join()
