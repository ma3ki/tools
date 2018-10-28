'''
-------------------------------------------------------
This script will at private domain function on UNBOUND.

This script needs ipcalc module.
How to install => pip install ipcalc

example listfiles)
private-domain.list
-------------------
yahoo.co.jp.
google.com.
-------------------

private-network.list
-------------------
133.242.186.90/32
2401:2500:102:1114:133:242:186:90/64
-------------------

Written by  : ma3ki@ma3ki.net
Release     : 1.00
Create date : 8 Feb 2014
-------------------------------------------------------
'''

### import python module
import os, sys, re

### set ipcalc module path
sys.path.append('/usr/lib/python2.7/site-packages')
import ipcalc

### private domain and client list path
scriptpath = "/var/unbound"
PDLIST = scriptpath + "/private-domain.list"
PNLIST = scriptpath + "/private-network.list"

#private domain and client list
PDOMAIN = []
V4LIST = []
V6LIST = []

#read lists
def _read_list():

  ### exists check lists
  for list in [ PDLIST, PNLIST ]:
    if os.path.exists(list) is False:
      log_info("pythonmod: %s is not found." % (list))
      return False

  ### read lists
  _read_domain(PDLIST)
  _read_network(PNLIST)

  return True

def _read_domain(pdlist):
  global PDOMAIN

  for line in open(pdlist,"r"):
    if re.match("^\w\S+\w\.$",line):
      PDOMAIN.append(line.rstrip())

def _read_network(pnlist):
  global V4LIST, V6LIST

  ipv4 = []
  ipv6 = []

  for line in open(pnlist,"r"):
    ipornet = line.rstrip()
    try:
      version = ipcalc.IP(ipornet).version()
      if version == 4:
        ipv4.append(ipornet)
      elif version == 6:
        ipv6.append(ipornet)
    except:
      pass

  V4LIST = [ipcalc.Network(ip) for ip in ipv4]
  V6LIST = [ipcalc.Network(ip) for ip in ipv6]

def _check_domain(domain):
  
  for pdomain in PDOMAIN:
    if domain.endswith("." + pdomain) or domain == pdomain:
      return True
  return False

def _check_network(clientip, domain):

  if ipcalc.IP(clientip).version() == 4:
    for network in V4LIST:
      if clientip in network:
        log_info("private=accept, network=%s, clientip=%s, query=%s" % (network,clientip,domain))
        return True
  elif ipcalc.IP(clientip).version() == 6:
    for network in V6LIST:
      if clientip in network:
        log_info("private=accept, network=%s, clientip=%s, query=%s" % (network,clientip,domain))
        return True
  log_info("private=reject, clientip=%s, query=%s" % (clientip,domain))
  return False

def setTTL(qstate, ttl):
  if qstate.return_msg:
    qstate.return_msg.rep.ttl = ttl
    if (qstate.return_msg.rep):
      for i in range(0,qstate.return_msg.rep.rrset_count):
        d = qstate.return_msg.rep.rrsets[i].entry.data
        for j in range(0,d.count+d.rrsig_count):
          d.rr_ttl[j] = ttl

def init(id, cfg):
  _read_list()
  return True

def deinit(id):
  return True

def inform_super(id, qstate, superqstate, qdata):
  return True

def operate(id, event, qstate, qdata):
  if (event == MODULE_EVENT_NEW) or (event == MODULE_EVENT_PASS):
    #pass the query to validator
    qstate.ext_state[id] = MODULE_WAIT_MODULE 
    return True

  if event == MODULE_EVENT_MODDONE:
    if not qstate.return_msg:
      qstate.ext_state[id] = MODULE_FINISHED 
      return True

    qdn = qstate.qinfo.qname_str
    if qstate.mesh_info.reply_list and qstate.mesh_info.reply_list.query_reply:
      q = qstate.mesh_info.reply_list.query_reply

      if _check_domain(qdn):

        if _check_network(q.addr,qdn) is False:
          qstate.return_rcode = RCODE_NXDOMAIN
          qstate.ext_state[id] = MODULE_FINISHED 
          return True
        else:
          setTTL(qstate, 0)

    qstate.return_rcode = RCODE_NOERROR
    qstate.ext_state[id] = MODULE_FINISHED 
    return True
      
  log_err("pythonmod: bad event")
  qstate.ext_state[id] = MODULE_ERROR
  return True
