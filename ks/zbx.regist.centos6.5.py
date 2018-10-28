#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ma3ki@ma3ki.net

from pyzabbix import ZabbixAPI, ZabbixAPIException
from requests import Session
import sys,re

CF = {
  "URL":"http://127.0.0.1/zabbix/",
  "BUSER":"",
  "BPASS":"",
  "ZUSER":"admin",
  "ZPASS":"zabbix",
  "GROUP":"Linux servers",
  "HOST":"example.com",
  "IP":"127.0.0.1",
  "TMPL":"Template OS Linux",
  "HTTPS": 0,
  "AUTH": 0,
}

def _usage():
  print """
  usage) ./regist.centos.py <URL=url> <BUSER=user> <BPASS=pass> <ZUSER=user> <ZPASS=pass> <GROUP=group> <HOST=host> <IP=ip> <TMPL=template>

    URL     zabbix web                    (default http://127.0.0.1/zabbix/)
    BUSER   basic authentication user     (default "")
    BPASS   basic authentication password (default "")
    ZUSER   zabbix user                   (default admin)
    ZPASS   zabbix password               (default zabbix)
    GROUP   zabbix host group             (default "Linux servers")
    HOST    hostname                      (default example.com)
    IP      ipaddress                     (default 127.0.0.1)
    TMPL    template name                 (default "Template OS Linux")
"""
  sys.exit(1)

def _readargv():
  if len(sys.argv) ==1:
    _usage()

  global CF

  cnt = 1
  while cnt < len(sys.argv):
    item = sys.argv[cnt]
    if re.match("^(URL|.USER|.PASS|GROUP|HOST|IP|TMPL)=",item):
      (subj,val) = item.split('=')
      CF[subj] = val
    else:
      _usage()
    cnt += 1

  if re.match("^https",CF['URL']):
    CF['HTTPS'] = 1
  if CF['BUSER'] != "":
    CF['AUTH'] = 1

def _chkhost(host):
  for h in zapi.host.get(output='extend'):
    if h['host'] == host:
      return 1
  return 0

def _chkgroup(group):
  for h in zapi.hostgroup.get(output='extend'):
    if h['name'] == group:
      return h['groupid']
  return 0

def _chktmpl(tmpl):
  for h in zapi.template.get(output='extend'):
    if h['name'] == tmpl:
      return h['templateid']
  return 0

def _createhost(gid,tid):
  hostid = zapi.host.create( \
  { \
    'host': CF['HOST'], \
    'available': 1, \
    'interfaces': \
      [{ \
         'type': 1, \
         'main': 1, \
         'useip': 1, \
         'ip': CF['IP'], \
         'dns': '', \
         'port': '10050', \
      }, \
      { \
         'type': 2, \
         'main': 1, \
         'useip': 1, \
         'ip': CF['IP'], \
         'dns': '', \
         'port': '161', \
      }], \
    'groups': \
      [{ \
         'groupid': gid, \
      }], \
    'templates': \
      [{ \
         'templateid': tid, \
      }], \
    'inventory_mode': 1, \
    'inventory': \
      {
        'os': 'Centos 6.5', \
      }, \
  })['hostids'][0]
  return hostid

if __name__ == '__main__':

  # read argv
  _readargv()

  # create zabbix session
  s = Session()

  # Enable HTTP auth
  if CF['AUTH'] == 1:
    s.auth = (CF['BUSER'],CF['BPASS'])

  # SSL
  if CF['HTTPS'] == 1:
    # Disable SSL certificate verification
    s.verify = False
    # ssl access
    try:
      zapi = ZabbixAPI(CF['URL'],s)
    except ZabbixAPIException as e:
      print(e)
  else:
    try:
      zapi = ZabbixAPI(CF['URL'])
    except ZabbixAPIException as e:
      print(e)

  # Login
  try:
    zapi.login(CF['ZUSER'],CF['ZPASS'])
  except ZabbixAPIException as e:
    print(e)

  print "Connected to Zabbix API Version %s" % zapi.api_version()

  if _chkhost(CF['HOST']) == 1:
    print "%s is already exist." % (CF['HOST'])
    sys.exit(1)

  grpid = _chkgroup(CF['GROUP'])
  if grpid == 0:
    print "%s group is not found." % (CF['GROUP'])
    sys.exit(1)

  tmplid = _chktmpl(CF['TMPL'])
  if tmplid == 0:
    print "%s template is not found." % (CF['TMPL'])
    sys.exit(1)

  # create host
  hostid = _createhost(grpid,tmplid)


