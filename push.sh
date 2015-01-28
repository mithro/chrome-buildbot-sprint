#! /bin/sh

# Two common locations people put google appengine
export PATH=$PATH:../google_appengine:./google_appengine

if ! which appcfg.py; then
	echo "Put appcfg in your path"
	exit
fi

(
	VER=$(git describe --dirty)-$USER
	cd appengine
	appcfg.py update app.yaml -V $VER
	appcfg.py set_default_version . -V $VER
)
