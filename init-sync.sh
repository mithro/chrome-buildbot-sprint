#!/bin/bash
/usr/share/google/safe_format_and_mount /dev/sdb /mnt/disk
export PATH=/mnt/disk/chromium/depot_tools:"$PATH"

