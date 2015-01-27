#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=2 sw=2 et sts=2 ai:

from __future__ import print_function

try:
  from termcolor import cprint as print_color
except ImportError:
  def print_color(*args, **kw):
    print(*args, **kw)

import threading
PRINT_LOCK = threading.RLock()

import sys
mainThread = threading.currentThread()
def info(type, value, tb):
  if hasattr(sys, 'ps1') or not sys.stderr.isatty() or threading.currentThread() != mainThread:
    # we are in interactive mode or we don't have a tty-like
    # device, so we call the default hook
    with PRINT_LOCK:
      print("+" * 80)
      print(threading.currentThread())
      sys.__excepthook__(type, value, tb)
      print("+" * 80)
  else:
    import traceback, pdb
    # we are NOT in interactive mode, print the exception...
    traceback.print_exception(type, value, tb)
    print
    # ...then start the debugger in post-mortem mode.
    pdb.pm()

sys.excepthook = info

init_old = threading.Thread.__init__
def init(self, *args, **kwargs):
    init_old(self, *args, **kwargs)
    run_old = self.run
    def run_with_except_hook(*args, **kw):
        try:
            run_old(*args, **kw)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.excepthook(*sys.exc_info())
    self.run = run_with_except_hook
threading.Thread.__init__ = init


from stages import *


PADDING=60
END=' | '
def pretty_print_status(t, skip_tid=False):
  if (isinstance(t, WaitOnOtherTasks)):
    pretty_print_status(t.task_to_run, skip_tid='/-> ')

  tid = t.tid
  if not skip_tid:
    padding = ' '*(PADDING - len(tid))
    print(padding, end='')

    tid = t.tid.split('-')
    print('-'.join(tid[:5]), end='-')
    print_color('-'.join(tid[5:]), color='cyan', end=' ')
    print('   ', end=END)
  else:
    print(' '*PADDING, end='')
    print(skip_tid, end=END)

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
  if isinstance(t, CancelledByOtherTask):
    pretty_print_status(t.task_to_run, skip_tid='\-> ')
  if not skip_tid:
    print()

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
        with PRINT_LOCK:
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

try:
  with PRINT_LOCK:
    print("SyncStage")
    print("-"*80)
    for t in SyncStage(previous_commit, current_commit).tasklets():
      pretty_print_status(t)

    if raw_input("okay? [y] ") not in ('y', ''):
      raise Exception("User aborted")

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
    with PRINT_LOCK:
      print("-" * 80)
      for t in SyncStage(previous_commit, current_commit).tasklets():
        pretty_print_status(t)
        if t.is_startable():
          if t.is_running():
            continue

          if t.is_finished():
            continue

          if raw_input("run (%s)? [n] " % t.tid) != 'y':
            continue

          def run(t=t):
            driver = libcloud_gae.new_driver()
            t.run(driver)
          threading.Thread(target=run).start()
      print("-" * 80)

    time.sleep(1)
finally:
  updater.go = False
  updater.join()


