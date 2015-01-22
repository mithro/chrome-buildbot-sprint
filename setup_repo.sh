#!/bin/bash
# Sets up the repo dependencies.
if [ ! -d libcloud ]; then
	git clone https://github.com/apache/libcloud.git
fi

if python -c "import backports.ssl_match_hostname"; then
	true
else
	sudo pip install backports.ssl-match-hostname
fi
if [ ! -e ../gce_bot_rsa ]; then
	echo "Need ssh key in ../gce_bot_rsa"
fi

if [ ! -e ../chrome-buildbot-sprint-c514ee5826d1.pem ]; then
	echo "Need gce API key in ../chrome-buildbot-sprint-c514ee5826d1.pem"
fi
