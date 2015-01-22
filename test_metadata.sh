#!/bin/bash

set -x
set -e

# gcloud compute project-info add-metadata --metadata callback="http://example.com/callback"

function cleanup {
	gcloud compute instances remove-metadata instance-1 --keys mount umount shutdown commands long-commands env
}

cleanup

gcloud compute instances add-metadata instance-1 --metadata mount='[{"mount-point": "/mnt/a", "disk-id": "empty-disk", "user": "ubuntu"}]'
gcloud compute instances add-metadata instance-1 --metadata umount='[{"mount-point": "/mnt/a", "disk-id": "empty-disk", "user": "ubuntu"}]'
gcloud compute instances add-metadata instance-1 --metadata commands='[{"cmd":"echo hello"}]'
gcloud compute instances add-metadata instance-1 --metadata long-commands='[{"cmd": "date; sleep 2; date; echo hello; cat /etc/passwd; sleep 5; date; echo hello; cat /etc/passwd; sleep 5; date; echo hello; cat /etc/passwd"}]'
gcloud compute instances add-metadata instance-1 --metadata shutdown="$(TZ=UTC date +%Y%m%d-%H%M%S)"
gcloud compute instances remove-metadata instance-1 --keys shutdown

gcloud compute project-info add-metadata --metadata env='{"p": "blah"}'
gcloud compute instances add-metadata instance-1 --metadata env='{"a": 1, "b": "hello"}'
gcloud compute instances add-metadata instance-1 --metadata commands='[{"cmd":"echo $a $b $p $(whoami)","user":"ubuntu"}]'
gcloud compute project-info remove-metadata --keys env
gcloud compute instances add-metadata instance-1 --metadata commands='[{"cmd":"echo $a $b $p"}]'

cleanup
