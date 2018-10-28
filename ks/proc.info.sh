#!/bin/sh
#
# usage) ./procinfo.sh <cpu|mem|rss|vsz|pnum|thread|info|swap> <process>
#
# 2014/04/26
# ma3ki@ma3ki.net v0.03 
# update 2014/05/21 add ) swap feature

export LANG=C
FILTER="*"
ZBXTMP=/var/tmp/.zbx_proc.cron.result

usage() {
  echo "usage) $0 <cpu|mem|rss|vsz|pnum|thread|info> <process> <filter>"
  echo "cpu    => cpu    usage percentage"
  echo "mem    => memory usage percentage"
  echo "rss    => memory usage RSS Bytes"
  echo "vsz    => memory usage VSZ Bytes"
  echo "swap   => swap   usage smaps Bytes"
  echo "pnum   => process count"
  echo "thread => process thread count"
  echo "info   => display process infomation"
  echo "tinfo  => display thread process infomation"
  echo "filter => command or \*"
  exit 1
}

### check
if [ $# -lt 2 ]
then
  usage
fi

if [ $# -gt 2 ]
then
  FILTER=$3
fi

### Get Process ID
PIDROOT=`pidof $2 | awk '{print $NF}'`

if [ "x" = "x${PIDROOT}" ]
then
  echo "ERROR: $2 process is not found."
  exit 2
fi

### Set Process ID list
PIDLIST=`pstree -a -p ${PIDROOT} 2>/dev/null | awk -F, '{print $2}' | awk '{print $1}' | awk '/^[0-9]+$/'`

### escape thread process
REALPIDLIST=`
for x in ${PIDLIST}
do
   awk -v p=$x '{if($2==$4 && $2==p)print $2}' ${ZBXTMP}
done
`

REALPIDLIST=`echo ${REALPIDLIST} | sed 's/ /,/g'`

export PIDENV=${REALPIDLIST}

### Get Data
case $1 in
  cpu)
    egrep "^Average:| CPU" ${ZBXTMP} | egrep "${FILTER}|CPU" | perl -ne '
      BEGIN{
        ($cpu,$use) = (0,0) ;
        %pmap ;
        foreach (split/,/,$ENV{"PIDENV"}) {
          $pmap{$_} = 1 ;
        }
      }
      if (/\((\d+)\s+CPU\)/) {
        $cpu = $1 ;
      }
      elsif (/^Average:\s+(\d+)\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)\s/) {
        if ( defined $pmap{$1} ) {
          $use += $2 ;
        }
      }
      END { printf "%f\n",$use/$cpu; }
    '
    ;;
  info|tinfo)
    export CMD=$1
    cat ${ZBXTMP} | perl -ne '
    BEGIN{
      %pmap ;
      foreach (split/,/,$ENV{"PIDENV"}) {
        $pmap{$_} = 1 ;
      }
    }
    if (/^\S+\s+(\d+)\s+\S+\s+(\S+)\s+/) {
      ($pid,$lwp) = ($1,$2) ;
      if ( $lwp =~ /\./ && defined $pmap{$pid} ) {
        print ;
      } elsif ( defined $pmap{$1} && $ENV{"CMD"} eq "tinfo" ) {
        print ;
      } elsif ( defined $pmap{$1} && $pid == $lwp ) {
        print ;
      }
    } elsif (/^$/) {
        next ;
    } else {
        print ;
    }
    '
    ;;
  vsz|rss|mem)
    export CMD=$1
    egrep "^[0-9]+:[0-9]+:[0-9]+" ${ZBXTMP} | egrep "${FILTER}" | perl -ne '
      BEGIN{
        %mem,%pmap ;
        foreach (split/,/,$ENV{"PIDENV"}) {
          $pmap{$_} = 1 ;
        }
      }
      if (/^\S+\s+(\d+)\s+[\d\.]+\s+[\d\.]+\s+(\d+)\s+(\d+)\s+([\d\.]+)\s+/) {
        if ( defined $pmap{$1} ) {
          $mem{"vsz"} += $2 ;
          $mem{"rss"} += $3 ;
          $mem{"mem"} += $4 ;
        }
      }
      END {
        if ( $ENV{"CMD"} eq "mem" ) {
          printf "%f\n", $mem{$ENV{"CMD"}} ;
        } else {
          printf "%d\n", $mem{$ENV{"CMD"}} * 1024 ;
        }
      }
    '
    ;;
  pnum)
    echo ${REALPIDLIST} | sed 's/,/\n/g' | wc -l
    ;;
  swap)
    for x in `echo ${REALPIDLIST} | sed 's/,/ /g'`
    do
      grep "^Swap:" /proc/$x/smaps 2>/dev/null
    done | awk '{T+=$2}END{print T*1024}'
    ;;
  thread)
    echo ${PIDLIST} | sed 's/ /\n/g' | wc -l
    ;;
  *)
    usage
    ;;
esac

exit 0
