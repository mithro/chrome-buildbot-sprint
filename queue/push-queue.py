#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:


import simplejson
import time
import urllib

snapshots = []
instances = []

def SnapshotExists(commit_id):
    return commit_id in snapshots

def InstanceExists(commit_id):
    return commit_id in instances

def InstanceStart(from_commit, new_commit):
    print "Launching instance for {0} based of {1}".format(from_commit, new_commit)
    instances.append(new_commit)

def UpdateState():
    time.sleep(5)
    while len(instances) > 0:
        commit_id = instances.pop(0)
        print "Completing {0}".format(commit_id)
        snapshots.append(commit_id)


while True:
    json = urllib.urlopen("https://chromium.googlesource.com/chromium/src/+log/master?format=json").read()
    json = "\n".join(json.splitlines()[1:])
    data = simplejson.loads(json)
    
    # Sort the commits into oldest first
    commit_ids = [entry['commit'] for entry in data['log']][::-1]
    commit_info = {entry['commit']: entry for entry in data['log']}

    snapshots.append(commit_ids[0])

    while True:
        for i, commit_id in enumerate(commit_ids[1:], 1):

            # If we already exist, then do nothing.
            if SnapshotExists(commit_id):
                continue

            # If we don't have a snapshot to start from, then just ignore the
            # commit.
            previous_commit_id = commit_ids[i-1]
            if not SnapshotExists(previous_commit_id):
                continue

            # If an instance is already trying to create a new snapshot, then
            # don't do anything.
            if InstanceExists(commit_id):
                continue

            # Start an instance up on this commit.
            else:
                InstanceStart(previous_commit_id, commit_id)

        UpdateState()
