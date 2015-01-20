#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:


import simplejson
import time
import urllib
import pprint

snapshots = {"src": {}, "build": {}, "test": {}}
instances = {"src": {}, "build": {}, "test": {}}

def SnapshotExists(mtype, commit_id):
    return commit_id in snapshots[mtype]

def InstanceExists(mtype, commit_id):
    return commit_id in instances[mtype]

def InstanceStart(mtype, new_commit, from_snapshot):
    assert from_snapshot[0] in snapshots
    assert from_snapshot[1] in snapshots[from_snapshot[0]]

    print "Launching {0} for {1} based of {2}".format(mtype, new_commit, from_snapshot)
    instances[mtype][new_commit] = time.time()

def LaunchInstances(commit_ids, instance_type, base_type):
    for i, commit_id in enumerate(commit_ids[1:], 1):
        # If we already exist, then do nothing.
        if SnapshotExists(instance_type, commit_id):
            continue

        # If we don't have a snapshot to start from, then just ignore the
        # commit.
        previous_commit_id = commit_ids[i-1]
        if not SnapshotExists(base_type, previous_commit_id):
            continue

        # If an instance is already trying to create a new snapshot, then
        # don't do anything.
        if InstanceExists(instance_type, commit_id):
            continue

        # Start an instance up on this commit.
        else:
            InstanceStart(instance_type, commit_id, from_snapshot=(base_type, previous_commit_id))

while True:
    json = urllib.urlopen("https://chromium.googlesource.com/chromium/src/+log/master?format=json").read()
    json = "\n".join(json.splitlines()[1:])
    data = simplejson.loads(json)
    
    # Sort the commits into oldest first
    commit_ids = [entry['commit'] for entry in data['log']][::-1]
    commit_info = {entry['commit']: entry for entry in data['log']}

    snapshots["src"][commit_ids[0]] = 0

    while True:
        # The source updater
        LaunchInstances(commit_ids, "src", "src")

        # The builders
        LaunchInstances(commit_ids, "build", "src")

        # The testers
        LaunchInstances(commit_ids, "test", "build")

        for mtype in instances:
            if mtype == "src":
                runtime = 2
            elif mtype == "build":
                runtime = 10
            elif mtype == "test":
                runtime = 7

            for commit_id in instances[mtype].keys():
                if (time.time() - instances[mtype][commit_id]) > runtime:
                    print "Completing {0} for {1}".format(mtype, commit_id)
                    snapshots[mtype][commit_id] = time.time()
                    del instances[mtype][commit_id]

        time.sleep(0.5)
        print "Running",
        for mtype in instances:
            print "%s %i" % (mtype, len(instances[mtype])), 
        print
