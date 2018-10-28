#!/bin/sh
#
# created by ma3ki@ma3ki.net
#
# usage ) ./cloudmessage.sh <GROUP> <TITLE> <MESSAGE>

DIR=/etc/zabbix/alertscripts
${DIR}/cloudmessage.py "$1" "$2" "$3" > /dev/null 2>&1 &

exit 0
