#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:


import simplejson
import time
import urllib

while True:
    json = urllib.urlopen("https://chromium.googlesource.com/chromium/src/+log/master?format=json").read()
    json = "\n".join(json.splitlines()[1:])
    data = simplejson.loads(json)
    
    # Sort the commits into oldest first
    commit_ids = [entry['commit'] for entry in data['log']][::-1]
    commit_info = {entry['commit']: entry for entry in data['log']}

    for i, commit_id in enumerate(commit_ids, 1):
        previous_commit_id = commit_ids[i-1]

        # If we don't have a snapshot to start from, then just ignore the
        # commit.
        if not SnapshotExists(previous_commit_id):
            continue

        # If an instance is already running, then don't do anything.
        if InstanceExists(type="snapshot_create", commit_id):
            continue

        # Start an instance up on this commit.
        InstanceStart(from_commit=commit_id)
