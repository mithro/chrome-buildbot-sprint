#!/bin/bash
# Sets up the repo dependencies.
git clone https://github.com/apache/libcloud.git
sudo pip install backports.ssl-match-hostname
