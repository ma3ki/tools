#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# 2012/08/05 v0.01: created by ma3ki@ma3ki.net
# 2013/04/17 v0.02: bug fix) the problem that could not transmit data beyond abount 1500byte.
# 2013/10/26 v0.03: add) Correspondence to zabbix version 2.2
# 2014/09/21 v0.04: add) feature file delete and sleep options
# 2015/09/12 v0.05: update
#
# This script has been tested by Zabbix 2.4 on CentOS 7.1 .
#
# Usage)
# ./zabbix_sender.py [-zpvS] {-ksot|-d -i <inputfile>}

import sys, os, socket, struct, re, random
from time import *

def usage():
  print """
usage) ./zabbix_sender.py [-zpvS] {-ksot|-d -i <inputfile>}
-z <server> : Hostname or IP address of Zabbix server. Default is 127.0.0.1.
-p <port>   : Port number of Zabbix server. Default is 10051.
-s <host>   : Specify host name as registered in Zabbix front-end. Host IP address and DNS name will not work.
-k <key>    : Specify key name as registered in Zabbix front-end.
-o <value>  : Specify value.
-t <clock>  : Specify epochtime.
-v          : Verbose mode
-i <file>   : Load values from zabbix_sender file. Each line of file contains comma and space delimited.
-d          : Delete file when data send is successful.
-S <num>    : Set max sleep time(seconds) before data send. Default is 0.

zabbix_sender format)
<hostname> <zabbix_key> <epochtime> <value>

example)
ma3ki.net zabbix_sender_key 1382828193 100
"""
  sys.exit()

def pack_data(listdata):
  msg = {}
  msg['data'] = []
  msg['request'] = 'sender data'
  msg['data'] = listdata
  msg = str(msg).replace('\"','').replace('\'','\"')

  data_length = len(msg)
  data_header = struct.pack('i', data_length) + '\0\0\0\0'
  data_to_send = 'ZBXD\1%s%s' % (data_header,msg)
  return data_to_send

# return 1 = error , 0 = ok
def send_data(zabbix,port,timeout,verbose,msg):
  ret = 0
  response_raw = ""

  ### make socket
  socket.setdefaulttimeout(timeout)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  try:
    ### connect to zabbix server
    sock.connect((zabbix, port))
    if verbose: print u'[connected to the zabbix server]\n%s:%d' % (zabbix,port)

    ### send the data to the server
    sock.sendall(msg)
    if verbose: print '[send message]\n%s' % (msg)

    ### read response msg, the first bytes are the header again
    response_header = sock.recv(5)

    if not response_header == 'ZBXD\1':
      sys.stderr.write('[ERROR]response failed\n')
      ret = 1
    response_data_header = sock.recv(8)
    response_data_header = response_data_header[:4]
    response_len = struct.unpack('i', response_data_header)[0]
    response_raw = sock.recv(response_len)
    if verbose: print u'[receive message]\n%s' % (response_raw)

    ### check response data
    if re.search('"response":"success",',response_raw) == False:
      sys.stderr.write('[ERROR]send failed\n')
      ret = 1
  except:
    sock.close()
    sys.stderr.write('[ERROR]connect failed\n')
    ret = 1
    
  sock.close()

  return ret
  
if __name__ == '__main__':

  ### set default value
  SERVER  = "127.0.0.1"
  PORT    = 10051
  TIMEOUT = 5
  VERBOSE = 0
  INPUTFILE = ""
  DELETE  = False
  SLEEP = 0

  data = {}
  data[0] = {}

  ### read options
  argvs = sys.argv
  scriptname = argvs.pop(0)

  while argvs:
    opt = argvs.pop(0)
    if opt == "-z":   SERVER = argvs.pop(0)
    elif opt == "-p": PORT = argvs.pop(0)
    elif opt == "-v": VERBOSE = 1
    elif opt == "-s": data[0]['host'] = argvs.pop(0)
    elif opt == "-k": data[0]['key'] = argvs.pop(0)
    elif opt == "-o": data[0]['value'] = argvs.pop(0)
    elif opt == "-t": data[0]['clock'] = argvs.pop(0)
    elif opt == "-i": INPUTFILE = argvs.pop(0)
    elif opt == "-d": DELETE = True
    elif opt == "-S": SLEEP = argvs.pop(0)
    else: usage()

  # zabbix_sender file check
  isFile = os.path.exists(INPUTFILE)

  if isFile == False:
    if INPUTFILE != "":
      sys.stderr.write("[ERROR]%s is not found.\n" % (INPUTFILE))
      sys.exit(1)
    ### if file is not found.
    if data[0].has_key('host')  == False: usage()
    if data[0].has_key('key')   == False: usage()
    if data[0].has_key('value') == False: usage()
    if data[0].has_key('clock') == False: data[0]['clock'] = int(time())
  else:
    i = 0
    f = open(INPUTFILE,"r")
    for line in f:
      match = re.match('^#',line)
      if match: continue
      line = line.rstrip()
      splist = re.split('[ ,]',line,3)
      data[i] = {}
      data[i]['host']  = splist[0]
      data[i]['key']   = splist[1]
      if len(splist) == 3:
        data[i]['clock'] = int(time())
        data[i]['value'] = splist[2]
      elif len(splist) == 4:
        data[i]['clock'] = splist[2]
        data[i]['value'] = splist[3]
      else: usage()
      i += 1
    f.close()

  ### send data
  if data[0] == {}:
    sys.stderr.write('[ERROR]data format error\n')
    sys.exit(1)

  (sendlist,splitdata,cnt,ret) = ([],100,0,0)
  for x in range(len(data)):
    if ( cnt >= splitdata ):
      sleep(random.uniform(0,int(SLEEP)))
      ret += send_data(SERVER,PORT,TIMEOUT,VERBOSE,pack_data(str(sendlist)))
      sendlist = []
      cnt = 0
    sendlist.append(data[x])
    cnt += 1
  sleep(random.uniform(0,int(SLEEP)))
  ret += send_data(SERVER,PORT,TIMEOUT,VERBOSE,pack_data(str(sendlist)))

  if isFile and ret == 0 and DELETE: os.remove(INPUTFILE)

  sys.exit(ret)
