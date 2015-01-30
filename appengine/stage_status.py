#!/usr/bin/python
#
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et sts=4 ai:

import libcloud_gae

import cgi
import os
import sys

from google.appengine.api import modules
from google.appengine.api import users
import webapp2

import jinja2

import stages

TEMPLATE_ENV = jinja2.Environment()
import pprint
TEMPLATE_ENV.filters['pprint'] = pprint.pformat

TEMPLATE_STAGE = TEMPLATE_ENV.from_string(
    open(os.path.join(os.path.dirname(__file__), 'stage-status.html')).read())

def get_exception():
    import traceback
    import cStringIO as StringIO
    f = StringIO.StringIO()
    traceback.print_exc(file=f)
    return f.getvalue()

class StageStatusHandler(webapp2.RequestHandler):
    def get(self, stage_type, previous_commit, current_commit):
        stage = getattr(stages, '%sStage' % stage_type.title())(previous_commit, current_commit)
        errors = []
        for t in stage.tasklets:
            if t.tid == self.request.get('go', ''):
                if not t.can_run():
                    errors.append("Skipping %s as it shouldn't run\n   (is_startable=%s, is_running=%s, is_finished=%s)" % (
                        t.tid, t.is_startable(), t.is_running(), t.is_finished()))
                    continue

                driver = libcloud_gae.new_driver()
                t.run(driver)

        self.response.out.write(TEMPLATE_STAGE.render(
            errors=errors,
            stage=stage,
            previous_commit=previous_commit,
            current_commit=current_commit)
            )

class StageCleanupHandler(webapp2.RequestHandler):
    def get(self, stage_type, previous_commit, current_commit):
        self.response.headers.add_header('Content-Type', 'text/plain')
        stage = getattr(stages, '%sStage' % stage_type.title())(previous_commit, current_commit)
        assert stage.needs_cleanup()
        driver = libcloud_gae.new_driver()
        stage.cleanup(driver)

