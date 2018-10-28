#!/bin/sh
#
# ma3ki@ma3ki.net
# 2014/04/26 v0.01

export LANG=C

RESULT=/var/tmp/.zbx_proc.cron.result
TEMPF=/var/tmp/.zbx_proc.cron.tmp

ps -efL > ${TEMPF} 2>&1
pidstat -r 2>&1 | grep -v 'CPU\$' >> ${TEMPF}
pidstat 55 1 2>&1 | egrep "^Average|CPU\)$" >> ${TEMPF}

cp -f ${TEMPF} ${RESULT}

exit 0

