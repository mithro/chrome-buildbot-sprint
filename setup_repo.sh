#!/bin/bash
# Sets up the repo dependencies.

if [ ! -d third_party/libcloud ]; then
	git clone https://github.com/apache/libcloud.git third_party/libcloud
fi

if [ ! -d third_party/backports.ssl_match_hostname-3.4.0.2 ]; then
	(cd third_party; wget -O- https://pypi.python.org/packages/source/b/backports.ssl_match_hostname/backports.ssl_match_hostname-3.4.0.2.tar.gz | tar -zxv)
fi

if [ ! -d third_party/python-dateutil-1.5 ]; then
  (cd third_party; wget -O- https://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz | tar -zxv)
fi

if [ ! -e keys/gce_bot_rsa ]; then
	echo "Need ssh key in keys/gce_bot_rsa"
fi

if [ ! -e keys/chrome-buildbot-sprint-c514ee5826d1.pem ]; then
	echo "Need gce API key in keys/chrome-buildbot-sprint-c514ee5826d1.pem"
fi

if [ ! -e appengine/whoami ]; then
	whoami > appengine/whoami
fi
