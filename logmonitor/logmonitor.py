#!/usr/bin/env python
#-*- coding: utf-8 -*-
#
# This script adds up log and a file, the result of the command.
#
# This script needs PyYAML module.
# How to install )
#   yum install PyYAML
#   yum install geoip python-GeoIP
#
# Written by  : ma3ki@ma3ki.net
# Version     : 1.17
# Create date : Oct 4th, 2014
# Last update : Aug 13th, 2017
#
# comment)
# 2017/08/13 v1.17: feature)
#   env を追加: command を実行する時に環境変数を指定できる
#   json の設定を読み込む機能を追加、URL指定可、指定しなければ json => yaml の順で読み込む
#   -m N オプションの追加。json をURL で指定した場合、N分毎に設定を取得する
#   json を読めるので yaml モジュールのインストールは必須でなくなった
#   sum のデフォルト type を int から float に変更
#   -vv オプションの追加: 詳細表示
#   -dry-run オプションの追加: zabbix-sender が on でも zabbix-sender しない
#   -s オプションの追加: config を JSONで見やすく表示する
# 2017/02/08 v1.16: feature) timeoutコマンドは存在した場合のみ使用する
# 2016/04/14 v1.15: feature) add send-change-data (default False) , don't send when value is 'no_match'
# 2016/04/01 v1.14: feature) add max-threads (default 5)
# 2016/03/30 v1.13: feature) add send-command-status (default False)
# 2016/03/22 v1.12: feature) support for a string of utf-8.
# 2016/03/04 v1.11: bug fix) text order
# 2016/02/26 v1.10: feature) add fqdn, ioCalc bug fix
# 2016/02/22 v1.09: feature) add zabbix-keyname
# 2016/01/06 v1.08: feature) add command.status item, change syslog format
# 2016/01/05 v1.07: feature) add text order
# 2015/12/31 v1.06: feature) add per-minutes
# 2015/12/28 v1.05: feature) add resource and ignore-resource
# 2015/09/24 v1.04: bug fix) _createTmpl
# 2015/09/17 v1.03: bug fix) _createTmpl
#
# usage)
# ./logmonitor.py [-f configfile] [-v|-vv] [-t[23] field] [-m N] [-s]
# -f: set configfile. (default: logmonitor.json => logmonitor.yaml)
# -m N: update json url config per N minutes
# -v: verbose mode
# -t2: output zabbix template file for version 2.0.
# -t3: output zabbix template file for version 3.0.
# -s: show config
# -dry-run: disable zabbix-sender

import os,sys,re,commands,codecs,shutil,syslog,threading,time,struct,socket,random,json,urllib2
from datetime import datetime,timedelta
from itertools import izip

OPT  = {}
CONF = {}
RESULT = {}
STATUS = {}
PATH = {}

COUNT = {}
UNIQ  = {}
MATCH = {}
SUM   = {}
GEOIP = {}
RESOURCE = []
LASTDATA = {}

GEOCODE = {}
GEONAME = {}

# 追加パッケージの確認
try:
  import yaml
  OPT['yaml'] = True
except:
  OPT['yaml'] = False
  pass
try:
  import GeoIP
  OPT['geoip'] = True
  GMC = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE)
except:
  OPT['geoip'] = False
  pass

OPT['CONF'] = ''
OPT['KIND'] = ''
OPT['TVERSION'] = '2.0'
OPT['VERBOSE'] = 0
OPT['PER-MINUTES'] = 5
OPT['GENERATION'] = 10
OPT['DRY-RUN'] = False
OPT['SHOW'] = False

def _usage():
  print "usage) ./logmonitor.py [-f configfile or json url] [-m N] [-v|-vv] [-t[23] field] [-s]"
  sys.exit(0)

def _initConfig():
  global CONF,RESULT,STATUS,UNIQ

  ### continue list
  clist = '^(command|file|log|rotation|rotation-time|generation|hostname|per-minutes|zabbix-keyname|fqdn|env)$'

  ### set default value
  CONF['config']['syslog']              = CONF['config'].get('syslog',False)
  CONF['config']['lock']                = CONF['config'].get('lock',False)
  CONF['config']['resource']            = CONF['config'].get('resource',False)
  CONF['config']['zabbix-sender']       = CONF['config'].get('zabbix-sender',False)
  CONF['config']['send-command-status'] = CONF['config'].get('send-command-status',False)
  CONF['config']['resource']            = CONF['config'].get('resource',False)
  CONF['config']['ignore-resource']     = CONF['config'].get('ignore-resource', '^$')

  ### init value
  for kind in CONF.keys():
    if kind == 'config' or kind == 'all': continue
    RESULT[kind] = {}
    STATUS[kind] = {}
    COUNT[kind] = {}
    UNIQ[kind] = {}
    SUM[kind] = {}
    GEOIP[kind] = {}
    MATCH[kind] = {}
    STATUS[kind]['line'] = 0
    STATUS[kind]['byte'] = 0
    STATUS[kind]['time'] = 0

    for order in CONF[kind].keys():
      if re.match(clist,order): continue
      RESULT[kind][order] = {}
      MATCH[kind][order] = {}
      for item in CONF[kind][order].keys():
        if order == 'text': RESULT[kind][order][item] = []
        else: RESULT[kind][order][item] = 0
        MATCH[kind][order][item] = {}
        if order == 'count': COUNT[kind][item] = {}
        if order == 'uniq_count': UNIQ[kind][item] = {}
        if order == 'sum' or order == 'average' : SUM[kind][item] = 0
        if order == 'geoip_count': GEOIP[kind][item] = {}

        for field in CONF[kind][order][item].keys():
          if re.search("^(filter|before|after)$",field):
            if re.search("^(geoip_count|text)$",order) and re.search("^(before|after)$",field):
              print "%s does not understand %s field." % (order,field)
              sys.exit(1)
            CONF[kind][order][item][field] = re.compile(CONF[kind][order][item][field])
          elif field == 'ignore':
            cnt = 0
            for ignore in CONF[kind][order][item][field]:
              CONF[kind][order][item][field][cnt] = re.compile(ignore)
              cnt += 1
        CONF[kind][order][item]['send-change-data'] = CONF[kind][order][item].get('send-change-data',False)

def _pasttime(starttime):
  pasttime = datetime.now() - starttime
  return pasttime.seconds + float(pasttime.microseconds)/1000000

def _lock(spath,flag):
  lpath = spath + 'lock'

  if flag == 'on':
    if os.path.isdir(lpath) is False:
      try:
        os.mkdir(lpath)
        _writeSyslog("lock=success, craete_lock_file=%s" % (lpath))
      except:
        _writeSyslog("lock=failed, message=cannot_make_directory(%s)" % (lpath))
        return 1
    else:
      _writeSyslog("lock=failed, message=%s is already exist." % (lpath))
      return 1
  elif flag == 'off':
    if os.path.isdir(lpath):
      try:
        os.rmdir(lpath)
        _writeSyslog("unlock=success, remove_lock_file=%s" % (lpath))
      except:
        _writeSyslog("unlock=failed, message=cannot_remove_directory(%s)" % (lpath))
        return 1
    else:
      _writeSyslog("unlock=failed, message=%s is not found." % (lpath))
      return 1
  return 0

def _dp(word):
  print "DEBUG %s" % (word)

def _ignore(kind,order,item,line,igkind):
  if CONF[kind][order][item].has_key(igkind):
    for ignore in CONF[kind][order][item][igkind]:
      if ignore.search(line):
        return False
  return True

def _filter_match(kind,order,item,key,value):
  global MATCH

  if value != "":
    if CONF[kind][order][item].has_key('before'):
      if MATCH[kind][order][item].has_key(key):
        return value
    elif CONF[kind][order][item].has_key('after'):
      MATCH[kind][order][item][key] = value
  else:
    if CONF[kind][order][item].has_key('before'):
      if MATCH[kind][order][item].has_key(key):
        return key
    elif CONF[kind][order][item].has_key('after'):
      MATCH[kind][order][item][key] = 1

  return ""

def _line_match(kind,order,item,when,line):
  global MATCH

  if CONF[kind][order][item].has_key(when):
    s = CONF[kind][order][item][when].search(line)
    if s:
      if when == 'before':
        MATCH[kind][order][item][s.group(1)] = 1
      elif when == 'after':
        if MATCH[kind][order][item].has_key(s.group(1)):
          return MATCH[kind][order][item][s.group(1)]
  return ""

def _geoip_code(ip):
  global GEOCODE

  if GEOCODE.has_key(ip) is False:
    GEOCODE[ip] = GMC.country_code_by_addr(ip)
  return GEOCODE[ip]

def _geoip_name(ip):
  global GEONAME

  if GEONAME.has_key(ip) is False:
    #GEONAME[ip] = GMC.country_name_by_addr(ip).replace(' ','_')
    GEONAME[ip] = str(GMC.country_name_by_addr(ip)).replace(' ','_')
  return GEONAME[ip]

def _geoip_count(kind,order,line):
  global RESULT,GEOIP

  for item in CONF[kind][order].keys():
    country = ""
    value  = ""
    if _ignore(kind,order,item,line,'ignore') is False: continue
    s = CONF[kind][order][item]['filter'].search(line)

    if s:
      if OPT['VERBOSE'] == 2: print "%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(1))
      if s.groupdict().has_key('code'):
        value = s.group('code')
        country = _geoip_code(s.group('code'))
      elif s.groupdict().has_key('name'):
        value = s.group('name')
        country = _geoip_name(s.group('name'))
      else:
        print "_geoip_count filter error"
        return 0

      if GEOIP[kind][item].has_key(country) is False:
        GEOIP[kind][item][country] = 0

      RESULT[kind][order][item] += 1
      GEOIP[kind][item][country] += 1

def _count(kind,order,line):
  global RESULT,COUNT

  for item in CONF[kind][order].keys():
    value = ""
    if _ignore(kind,order,item,line,'ignore') is False: continue
    s = CONF[kind][order][item]['filter'].search(line)

    if s:
      if OPT['VERBOSE'] == 2: print "%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(1))
      if s.groupdict().has_key('value'):
        value = s.group('value')
      elif s.groupdict().has_key('value') is False and s.groupdict().has_key('match') is False:
        if len(s.groups()) == 1:
          value = s.group(1)

      if COUNT[kind][item].has_key(value) is False:
        COUNT[kind][item][value] = 0

      if s.groupdict().has_key('match'):
        fmresult = _filter_match(kind,order,item,s.group('match'),"")
        ### with before
        if fmresult != "":
          RESULT[kind][order][item] += 1
          COUNT[kind][item][value] += 1
      ### only filter
      else:
        RESULT[kind][order][item] += 1
        COUNT[kind][item][value] += 1

    elif CONF[kind][order][item].has_key('before'):
      _line_match(kind,order,item,'before',line)

    elif CONF[kind][order][item].has_key('after'):
      lmresult = _line_match(kind,order,item,'after',line)
      if lmresult != "":
        RESULT[kind][order][item] += 1
        COUNT[kind][item][lmresult] += 1

def _uniq_count(kind,order,line):
  global RESULT,UNIQ

  for item in CONF[kind][order].keys():
    value = ""
    if _ignore(kind,order,item,line,'ignore') is False: continue
    s = CONF[kind][order][item]['filter'].search(line)

    if s:
      if OPT['VERBOSE'] == 2: print "%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(1))
      if s.groupdict().has_key('value'):
        value = s.group('value')
      elif s.groupdict().has_key('value') is False and s.groupdict().has_key('match') is False:
        if len(s.groups()) == 1:
          value = s.group(1)

      if s.groupdict().has_key('match'):
        fmresult = _filter_match(kind,order,item,s.group('match'),value)
        ### with before
        if fmresult != "":
          if UNIQ[kind][item].has_key(value) is False:
            RESULT[kind][order][item] += 1
            UNIQ[kind][item][value] = 1
      ### only filter
      else:
        if UNIQ[kind][item].has_key(value) is False:
          RESULT[kind][order][item] += 1
          UNIQ[kind][item][value] = 1

    elif CONF[kind][order][item].has_key('before'):
      _line_match(kind,order,item,'before',line)

    elif CONF[kind][order][item].has_key('after'):
      lmresult = _line_match(kind,order,item,'after',line)
      if lmresult != "":
        if UNIQ[kind][item].has_key(lmresult) is False:
          RESULT[kind][order][item] += 1
          UNIQ[kind][item][lmresult] = 1

def _text(kind,order,line):
  global RESULT

  for item in CONF[kind][order].keys():
    vgroup = []
    value = ""
    if _ignore(kind,order,item,line,'ignore') is False: continue

    s = CONF[kind][order][item]['filter'].search(line)
    if s:
      if OPT['VERBOSE'] == 2: print "%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(1))
      if s.groupdict().has_key('value'):
        vgroup.append(s.group('value'))
        value = vgroup[0]
      elif s.groupdict().has_key('value') is False and s.groupdict().has_key('match') is False:
        for x in range(0,len(s.groups())):
          vgroup.append(s.group(x+1))
        if len(vgroup) > 0: value = vgroup[0]
      if value == "": value = line
      RESULT[kind][order][item].append(value.rstrip())

def _sum(kind,order,line):
  global RESULT,SUM

  for item in CONF[kind][order].keys():
    value = ""
    vgroup = []

    if _ignore(kind,order,item,line,'ignore') is False: continue
    s = CONF[kind][order][item]['filter'].search(line)

    if s:
      if OPT['VERBOSE'] == 2: print "%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(1))
      if s.groupdict().has_key('value'):
        vgroup.append(s.group('value'))
      elif s.groupdict().has_key('value') is False and s.groupdict().has_key('match') is False:
        for x in range(0,len(s.groups())):
          vgroup.append(s.group(x+1))

      if CONF[kind][order][item].has_key('calc'):
        calc = CONF[kind][order][item]['calc']
        for x in range(0,len(s.groups())):
          x += 1
          calc = str(calc.replace('$' + str(x),s.group(x)))
        value = eval(calc)
      else:
        value = vgroup[0]

      if s.groupdict().has_key('match'):
        fmresult = _filter_match(kind,order,item,s.group('match'),value)
        ### with before
        if fmresult != "":
          RESULT[kind][order][item] += float(fmresult)
          SUM[kind][item] += 1
      ### only filter
      else:
        RESULT[kind][order][item] += float(value)
        SUM[kind][item] += 1

    elif CONF[kind][order][item].has_key('before'):
      _line_match(kind,order,item,'before',line)

    elif CONF[kind][order][item].has_key('after'):
      lmresult = _line_match(kind,order,item,'after',line)
      if lmresult != "":
        RESULT[kind][order][item] += float(lmresult)
        SUM[kind][item] += 1

def _command(kind,command):
  global RESULT
  command = '%s' % command.encode('utf-8')
  if os.path.exists('/usr/bin/timeout'):
    command = '/usr/bin/timeout 30 %s' % command.encode('utf-8')
  if CONF[kind].has_key('env'):
    command = CONF[kind]['env'] + " " + command
  _writeSyslog("command=start, kind=%s, command=\"%s\"" % (kind,command))
  result = commands.getstatusoutput(command)
  RESULT[kind]['status'] = result[0]

  if result[0] == 0:
    for line in result[1].split('\n'):
      if line == "": continue
      if CONF[kind].has_key('count'): _count(kind,'count',line)
      if CONF[kind].has_key('uniq_count'): _uniq_count(kind,'uniq_count',line)
      if CONF[kind].has_key('sum'): _sum(kind,'sum',line)
      if CONF[kind].has_key('average'): _sum(kind,'average',line)
      if CONF[kind].has_key('text'): _text(kind,'text',line)
      if CONF[kind].has_key('geoip_count'):
        if OPT['geoip']: _geoip_count(kind,'geoip_count',line)
        else: print "geoip module is not installed"
    _writeSyslog("command=finish, kind=%s, command=\"%s\", status=%s" % (kind,command,result[0]))
  else:
    if result[0] == 31744:
      _writeSyslog("command=finish, kind=%s, command=\"%s\", status=%s, stderr=\"%s\"" % (kind,command,result[0],'command timeout'))
    else:
      _writeSyslog("command=finish, kind=%s, command=\"%s\", status=%s, stderr=\"%s\"" % (kind,command,result[0],result[1]))

def _openfile(kind,file):

  _writeSyslog("openfile=start, kind=%s, openfile=%s" % (kind,file))

  if os.path.exists(file) is False:
    _writeSyslog("kind=%s, openfile=%s, message=file_is_not_found" % (kind,file))
    return False

  f = codecs.open(file,'r')
  for line in f.readlines():
    if line == "": continue
    if CONF[kind].has_key('count'): _count(kind,'count',line)
    if CONF[kind].has_key('uniq_count'): _uniq_count(kind,'uniq_count',line)
    if CONF[kind].has_key('sum'): _sum(kind,'sum',line)
    if CONF[kind].has_key('average'): _sum(kind,'average',line)
    if CONF[kind].has_key('text'): _text(kind,'text',line)
    if CONF[kind].has_key('geoip_count'):
      if OPT['geoip']: _geoip_count(kind,'geoip_count',line)
      else: print "geoip module is not installed"
  f.close()

  _writeSyslog("openfile=finish, kind=%s, openfile=%s" % (kind,file))

def _openlog(kind,log):
  global STATUS

  _writeSyslog("openlog=start, kind=%s, openlog=%s" % (kind,log))

  if os.path.exists(log) is False:
    _writeSyslog("kind=%s, openlog=%s, message=log_is_not_found" % (kind,log))
    return False

  f = codecs.open(log,'r')
  if STATUS[kind].has_key('handler') and STATUS[kind]['rotate'] is False:
    f.seek(STATUS[kind]['handler']+1)
  for line in f.readlines():
    if line == "": continue
    if CONF[kind].has_key('count'): _count(kind,'count',line)
    if CONF[kind].has_key('uniq_count'): _uniq_count(kind,'uniq_count',line)
    if CONF[kind].has_key('sum'): _sum(kind,'sum',line)
    if CONF[kind].has_key('average'): _sum(kind,'average',line)
    if CONF[kind].has_key('text'): _text(kind,'text',line)
    if OPT['geoip']:
      if CONF[kind].has_key('geoip_count'): _geoip_count(kind,'geoip_count',line)
    if STATUS[kind].has_key('firstline') is False:
      STATUS[kind]['firstline'] = line.replace('\n','')
    STATUS[kind]['line'] += 1
    STATUS[kind]['byte'] += len(line)
    STATUS[kind]['lastline'] = line.replace('\n','')
  STATUS[kind]['handler'] = f.tell()
  f.close()

  _writeSyslog("openlog=finish, kind=%s, openlog=%s" % (kind,log))

  return True

def _readlog(kind):
  global STATUS,CONF,RESULT

  STATUS[kind]['time'] = datetime.now()
  STATUS[kind]['unixtime'] = datetime.now().strftime('%s')
  STATUS[kind]['rotate'] = False

  if CONF[kind].has_key('log'):
    CONF[kind]['log'] = datetime.now().strftime(CONF[kind]['log'])

  if STATUS[kind].has_key('inode'):
    try:
      if os.stat(CONF[kind]['log']).st_ino != int(STATUS[kind]['inode']):
        if CONF[kind].has_key('rotation-time'):
          cdate = _changeTime(CONF[kind]['rotation-time'])
          logdate = datetime.now() - timedelta(cdate[0],cdate[1])
          _openlog(kind,logdate.strftime(CONF[kind]['rotation']))
        else:
          _openlog(kind,datetime.now().strftime(CONF[kind]['rotation']))
        STATUS[kind]['rotate'] = True
    except:
      pass

  if CONF[kind].has_key('log'):
    if _openlog(kind,CONF[kind]['log']):
      STATUS[kind]['inode'] = os.stat(CONF[kind]['log']).st_ino
    else:
      del CONF[kind]
      del RESULT[kind]
      return False
  if CONF[kind].has_key('command'):
    _command(kind,CONF[kind]['command'])
  if CONF[kind].has_key('file'):
    _openfile(kind,CONF[kind]['file'])

  STATUS[kind]['time'] = _pasttime(STATUS[kind]['time'])

def _result():
  for kind in RESULT.keys():
    unixtime = STATUS[kind]['unixtime']
    if CONF[kind].has_key('hostname'):
      hostname = CONF[kind]['hostname']
    else:
      hostname = CONF['config']['hostname']
    if CONF['config'].get('fqdn',True) is True:
      pass
    else:
      hostname = hostname.split('.')[0]
    for order in sorted(RESULT[kind].keys()):
      if order == 'status':
        _writeResult(kind,order,"%s %s.status %s %d" % (hostname,kind,unixtime,RESULT[kind][order]))
        continue
      if re.match('^(count|uniq_count)$',order): type = 'integer'
      if re.match('^(average|sum)$',order): type = 'float'
      if re.match('^geoip_count$',order): type = 'strings'
      for item in sorted(RESULT[kind][order].keys()):
        (top,display,others,count,total) = (10,'value',True,0,0)
        if CONF[kind][order][item].has_key('top'): top = CONF[kind][order][item]['top']
        if CONF[kind][order][item].has_key('others'): others = CONF[kind][order][item]['others']
        if CONF[kind][order][item].has_key('display'): display = CONF[kind][order][item]['display']
        if CONF[kind][order][item].has_key('type'): type = CONF[kind][order][item]['type']

        if order == 'count':
          if display == 'list':
            if len(COUNT[kind][item]) == 0:
              _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,"no_match"))
            for key, value in sorted(COUNT[kind][item].items(), key=lambda x:int(x[1]), reverse=True):
              count += 1
              if value > 0: _writeResult(kind,order,"%s %s %s %s=%d" % (hostname,item,unixtime,key,value))
              _valueOverExec(kind,order,item,value,key)
              total += value
              if count == top and others == True:
                if RESULT[kind][order][item] - total <= 0: break
                _writeResult(kind,order,"%s %s %s %s=%d" % (hostname,item,unixtime,'Others',RESULT[kind][order][item] - total))
                break
              elif count == top and others == False: break
          elif display == 'value':
            _valueOverExec(kind,order,item,RESULT[kind][order][item])
            _writeResult(kind,order,"%s %s %s %d" % (hostname,item,unixtime,RESULT[kind][order][item]))
        elif order == 'text':
          for text in RESULT[kind][order][item]:
            _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,text))
            count += 1
            if count >= top: break
        elif order == 'geoip_count':
          display = 'list'
          if CONF[kind][order][item].has_key('display'): display = CONF[kind][order][item]['display']
          if display == 'list':
            if len(GEOIP[kind][item]) == 0:
              _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,"no_match"))
            for key, value in sorted(GEOIP[kind][item].items(), key=lambda x:int(x[1]), reverse=True):
              count += 1
              if value > 0: _writeResult(kind,order,"%s %s %s %s=%d" % (hostname,item,unixtime,key,value))
              _valueOverExec(kind,order,item,value,key)
              total += value
              if count == top and others == True:
                if RESULT[kind][order][item] - total <= 0: break
                _writeResult(kind,order,"%s %s %s %s=%d" % (hostname,item,unixtime,'Others',RESULT[kind][order][item] - total))
                break
              elif count == top and others == False: break
          elif re.search("^\S+,\S+$",display):
            for code in display.split(','):
              if GEOIP[kind][item].has_key(code) is False: GEOIP[kind][item][code] = 0
              _writeResult(kind,order,"%s %s %s %d" % (hostname,item+'['+code+']',unixtime,GEOIP[kind][item][code]))
              _valueOverExec(kind,order,item,GEOIP[kind][item][code],code)
              total += GEOIP[kind][item][code]
            if others == True:
              if RESULT[kind][order][item] - total <= 0: break
              _writeResult(kind,order,"%s %s %s %d" % (hostname,item+'[Others]',unixtime,RESULT[kind][order][item] - total))
        elif re.search('^(sum|average|uniq_count)$',order):
          if order == 'average':
            value = 0
            if SUM[kind][item] > 0:
              value = RESULT[kind][order][item]/SUM[kind][item]
          else:
            value = RESULT[kind][order][item]
          try:
            if type == 'integer':
              value = int(value)
              _writeResult(kind,order,"%s %s %s %d" % (hostname,item,unixtime,value))
            elif type == 'float':
              value = float(value)
              _writeResult(kind,order,"%s %s %s %.3f" % (hostname,item,unixtime,value))
            else:
              value = str(value)
              _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,value))
          except:
            if CONF[kind].has_key('zabbix-keyname'):
              item += '[%s]' % CONF[kind]['zabbix-keyname']
            _writeSyslog("kind=%s, host=%s, item=%s, value=%s, message=type_failed" % (kind,hostname,item,value))
            value = str(value)
            _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,value))
          _valueOverExec(kind,order,item,value)

  for x in RESOURCE:
    _writeResult('config','resource',"%s" % (x))

def _valueOverExec(kind,order,item,value,key=""):

  for x in ['min-limit','max-limit']:
    execflag = False
    if CONF[kind][order][item].has_key(x):
      if x == 'min-limit' and value < int(CONF[kind][order][item][x]): execflag = True
      if x == 'max-limit' and value > int(CONF[kind][order][item][x]): execflag = True
    if CONF[kind][order][item].has_key(x + '-over-exec') and execflag:
      if CONF[kind].has_key('zabbix-keyname'):
        item += '%s[%s]' % (item,CONF[kind]['zabbix-keyname'])
      if key != "":
        command = CONF[kind][order][item][x + '-over-exec'].replace('$key',key).encode('utf-8')
        _writeSyslog("kind=%s, item=%s, key=%s, value=%s, %s=%s, %s-over-exec=\"%s\"" % (kind,item,key,value,x,CONF[kind][order][item][x],x,command))
      else:
        command = CONF[kind][order][item][x + '-over-exec'].encode('utf-8')
        _writeSyslog("kind=%s, item=%s, value=%s, %s=%s, %s-over-exec=\"%s\"" % (kind,item,value,x,CONF[kind][order][item][x],x,command))
      result = commands.getstatusoutput(command)
      if OPT['VERBOSE']: print result

def _writeResult(kind,order,output):
  sendflag = False
  host, item, unixtime, value = output.split(' ',3)
  if CONF[kind].has_key('zabbix-keyname'):
    item += '[%s]' % CONF[kind]['zabbix-keyname']
  output = "%s %s %s %s" % (host,item,unixtime,value)

  if kind != 'config':
    f = codecs.open(CONF[kind]['result'],'a')
    f.write(output + '\n')
    f.close()

  scdflag = False
  try:
    if CONF[kind][order][item]['send-change-data']:
      scdflag = True
  except:
    pass

  if re.search('\.status$',item) and CONF['config']['send-command-status'] is False:
    pass
  elif value == 'no_match':
    pass
  elif scdflag:
      if _checkLastData(host,item,value):
        sendflag = True
        f = codecs.open(CONF['config']['result'],'a')
        f.write(output + '\n')
        f.close()
  else:
    sendflag = True
    f = codecs.open(CONF['config']['result'],'a')
    f.write(output + '\n')
    f.close()

  if re.search("=\d+$",value):
    output = "zsend=%s, host=%s, item=%s, %s" % (sendflag,host,item,value)
  else:
    output = "zsend=%s, host=%s, item=%s, value=%s" % (sendflag,host,item,value)

  _writeSyslog("kind=%s, %s" %(kind,output))
  time.sleep(random.uniform(0,0.05))

def _writeSyslog(output):
  if OPT['VERBOSE']: print output
  if CONF['config']['syslog']:
    try:
      syslog.syslog(syslog.LOG_INFO,output)
    except:
      syslog.syslog(syslog.LOG_INFO,'syslog output failed')

def _renameResult(path,kind):
  global CONF
  result = ""

  if kind == 'config':
    CONF[kind]['result'] = path + 'all' + '.result'

  if CONF[kind].has_key('result') is False:
    result = path + kind + '.result'
    CONF[kind]['result'] = result
  else:
    result = CONF[kind]['result']

  generation = OPT['GENERATION']
  if CONF[kind].has_key('generation'):
    generation = int(CONF[kind]['generation'])
  for x in range(generation, 0, -1):
    if x == 1:
      if os.path.exists(result):
        os.rename(result,result+'.'+str(x))
    elif os.path.exists(result+'.'+str(x-1)):
      os.rename(result+'.'+str(x-1), result+'.'+str(x))

def _readStatus(path,kind):
  global STATUS

  status = path + kind + '.status'
  if os.path.exists(status):
    for line in codecs.open(status,'r'):
      m = re.match('^(\S+)=(\S+)$',line)
      if m:
        if m.group(2).isdigit():
          STATUS[kind][m.group(1)] = int(m.group(2))
        else:
          STATUS[kind][m.group(1)] = m.group(2)
  ### init
  STATUS[kind]['line'] = 0
  STATUS[kind]['byte'] = 0
  STATUS[kind]['time'] = 0

def _updateStatus(path,kind):
  status = path + kind + '.status'
  #f = codecs.open(status,'w','utf-8')
  f = codecs.open(status,'w')
  for field in STATUS[kind].keys():
    f.write('%s=%s\n' % (field,STATUS[kind][field]))
  f.close

def _changeTime(value):
  result = [0,0]
  m = re.match('^-(\d+)([dhms])$',value)
  if m:
    num = int(m.group(1))
    unit = m.group(2)
    if unit == "d": result[0] = num
    if unit == "h": result[1] = 3600 * num
    if unit == "m": result[1] = 60 * num
    if unit == "s": result[1] = num
  return result

def _readOption():
  ## nothing arguments
  if len(sys.argv) == 1:
    return

  global OPT
  cnt = 1
  while cnt < len(sys.argv):
    val = sys.argv[cnt]
    if val == '-f':
      cnt += 1
      try:
        OPT['CONF'] = sys.argv[cnt]
      except:
        _usage()
    elif val == '-v':
      OPT['VERBOSE'] = 1
    elif val == '-vv':
      OPT['VERBOSE'] = 2
    elif val == '-dry-run':
      OPT['DRY-RUN'] = True
    elif val == '-s':
      OPT['SHOW'] = True
    elif val == '-m':
      cnt += 1
      try:
        OPT['PER-MINUTES'] = sys.argv[cnt]
      except:
        _usage()
    elif re.match('^-t',val):
      m = re.match('^-t([23])$',val)
      if m: OPT['TVERSION'] = str(m.group(1)) + '.0'
      cnt += 1
      try:
        OPT['KIND'] = sys.argv[cnt]
      except:
        _usage()
    else:
      _usage()
    cnt += 1

def _createTmpl(kind,version):

  from xml.etree.ElementTree import Element, SubElement, Comment
  from xml.etree import ElementTree
  from xml.dom import minidom

  global CONF
  if kind == 'logmonitor':
    CONF[kind] = {}
    CONF[kind]['text'] = {}
    item = "lock"
    if CONF['config'].has_key('lock-item'): item = CONF['config']['lock-item']
    CONF[kind]['text'][item] = {}

  if CONF.has_key(kind) == False:
    print "%s_field is not found." % (kind)
    sys.exit(1)

  def prettify(elem):
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

  date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
  application = "logmonitor"

  top = Element('zabbix_export')
  c1_version      = SubElement(top, 'version')
  c1_version.text = version
  c1_date         = SubElement(top, 'date')
  c1_date.text    = date
  c1_groups       = SubElement(top, 'groups')
  c2_group        = SubElement(c1_groups, 'group')
  c3_name         = SubElement(c2_group, 'name')
  c3_name.text    = application

  c1_templates      = SubElement(top, 'templates')
  c2_template       = SubElement(c1_templates, 'template')
  c3_template       = SubElement(c2_template, 'template')
  c3_template.text  = 'Template_Trapper_' + kind
  c3_name           = SubElement(c2_template, 'name')
  c3_name.text      = 'Template_Trapper_' + kind
  c3_descripion     = SubElement(c2_template, 'description')

  c3_groups         = SubElement(c2_template, 'groups')
  c4_group          = SubElement(c3_groups, 'group')
  c5_name           = SubElement(c4_group, 'name')
  c5_name.text      = application

  c3_applications   = SubElement(c2_template, 'applications')
  c4_application    = SubElement(c3_applications, 'application')
  c5_name           = SubElement(c4_application, 'name')
  c5_name.text      = application

  c3_items      = SubElement(c2_template, "items")
  for order in CONF[kind].keys():
    if re.match("^(file|hostname|log|rotation|rotation-time|per-minutes|zabbix-keyname|fqdn|env)$",order): continue
    if re.match('^(count|uniq_count)$',order): type = 'integer'
    if re.match('^(average|sum)$',order): type = 'float'
    if re.match('^(geoip_count|text)$',order): type = 'strings'
    if order == 'command':
      command = CONF[kind]['command']
      CONF[kind]['command'] = {}
      if CONF['config']['send-command-status']:
        CONF[kind]['command']["%s.status" % (kind)] = {}
        CONF[kind]['command']["%s.status" % (kind)]['command'] = command
      type = 'integer'

    for item in CONF[kind][order].keys():
      if CONF[kind][order][item].has_key('type'): type = CONF[kind][order][item]['type']

      if CONF[kind].has_key('zabbix-keyname'):
        item += '[%s]' % CONF[kind]['zabbix-keyname']

      c4_item                   = SubElement(c3_items, "item")
      c5_name                   = SubElement(c4_item, "name")
      c5_name.text              = "%s" % (item)
      c5_type                   = SubElement(c4_item, "type")
      c5_type.text              = "2"
      c5_snmp_community         = SubElement(c4_item, "snmp_community")
      c5_multiplier             = SubElement(c4_item, "multiplier")
      c5_multiplier.text        = "0"
      c5_snmp_oid               = SubElement(c4_item, "snmp_oid")
      c5_key                    = SubElement(c4_item, "key")
      c5_key.text               = item
      c5_delay                  = SubElement(c4_item, "delay")
      c5_delay.text             = "0"
      c5_history                = SubElement(c4_item, "history")
      c5_history.text           = "90"
      c5_trends                 = SubElement(c4_item, "trends")
      c5_status                 = SubElement(c4_item, "status")
      c5_status.text            = "0"
      c5_value_type             = SubElement(c4_item, "value_type")

      if type == 'integer':
        c5_trends.text          = "365"
        c5_value_type.text      = "3"
      elif type == 'float':
        c5_trends.text          = "365"
        c5_value_type.text      = "0"
      elif type == 'strings':
        c5_trends.text          = "0"
        c5_value_type.text      = "4"
      else:
        c5_trends.text          = "0"
        c5_value_type.text      = "1"

      c5_allowed_hosts          = SubElement(c4_item, "allowed_hosts")
      c5_units                  = SubElement(c4_item, "units")
      c5_delta                  = SubElement(c4_item, "delta")
      c5_delta.text             = "0"
      c5_snmpv3_contextname     = SubElement(c4_item, "snmpv3_contextname")
      c5_snmpv3_securityname    = SubElement(c4_item, "snmpv3_securityname")
      c5_snmpv3_securitylevel   = SubElement(c4_item, "snmpv3_securitylevel")
      c5_snmpv3_securitylevel.text = "0"
      c5_snmpv3_authprotocol    = SubElement(c4_item, "snmpv3_authprotocol")
      c5_snmpv3_authprotocol.text = "0"
      c5_snmpv3_authpassphrase  = SubElement(c4_item, "snmpv3_authpassphrase")
      c5_snmpv3_privprotocol    = SubElement(c4_item, "snmpv3_privprotocol")
      c5_snmpv3_privprotocol.text = "0"
      c5_snmpv3_privpassphrase  = SubElement(c4_item, "snmpv3_privpassphrase")
      c5_formula                = SubElement(c4_item, "formula")
      c5_formula.text           = "1"
      c5_delay_flex             = SubElement(c4_item, "delay_flex")
      c5_params                 = SubElement(c4_item, "params")
      c5_ipmi_sensor            = SubElement(c4_item, "ipmi_sensor")
      c5_data_type              = SubElement(c4_item, "data_type")
      c5_data_type.text         = "0"
      c5_authtype               = SubElement(c4_item, "authtype")
      c5_authtype.text          = "0"
      c5_username               = SubElement(c4_item, "username")
      c5_password               = SubElement(c4_item, "password")
      c5_publickey              = SubElement(c4_item, "publickey")
      c5_privatekey             = SubElement(c4_item, "privatekey")
      c5_port                   = SubElement(c4_item, "port")
      c5_description            = SubElement(c4_item, "description")
      c5_inventory_link         = SubElement(c4_item, "inventory_link")
      c5_inventory_link.text    = "0"
      c5_applications           = SubElement(c4_item, "applications")
      c6_application            = SubElement(c5_applications, "application")
      c7_name                   = SubElement(c6_application, "name")
      c7_name.text              = application
      c5_valuemap               = SubElement(c4_item, "valuemap")
      c5_logtimefmt             = SubElement(c4_item, "logtimefmt")

  c3_discovery_rules      = SubElement(c2_template, 'discovery_rules')
  c3_macros               = SubElement(c2_template, 'macros')
  c3_templates            = SubElement(c2_template, 'templates')
  c3_screens              = SubElement(c2_template, 'screens')

  for order in CONF[kind].keys():
    if order != 'command': continue
    c1_triggers      = SubElement(top, 'triggers')
    for item in CONF[kind][order].keys():
      c2_trigger       = SubElement(c1_triggers, 'trigger')
      c3_expression    = SubElement(c2_trigger, 'expression')
      c3_expression.text  = '{Template_Trapper_' + kind + ':' + item + '.last()}&gt;0'
      c3_name          = SubElement(c2_trigger, 'name')
      c3_name.text     = 'logmonitor command error'
      c3_url           = SubElement(c2_trigger, 'url')
      c3_status        = SubElement(c2_trigger, 'status')
      c3_status.text   = '0'
      c3_priority      = SubElement(c2_trigger, 'priority')
      c3_priority.text = '3'
      c3_description   = SubElement(c2_trigger, 'description')
      c3_description.text  = 'command error: %s' % (CONF[kind][order][item]['command'])
      c3_type          = SubElement(c2_trigger, 'type')
      c3_type.text     = '0'
      c3_dependencies  = SubElement(c2_trigger, 'dependencies')

  print prettify(top).replace('&amp;','&').replace('&gt;','>')

def _zabbix_sender(zabbix,path,file,mode):
  if OPT['DRY-RUN']: return 0

  (server,port) = zabbix.split("@")
  port = int(port)
  ### default set
  (timeout,sleep,rsleep,limit) = (15,1,1,10000000)
  if CONF['config'].has_key('zabbix-sender-timeout'): timeout = int(CONF['config']['zabbix-sender-timeout'])
  if CONF['config'].has_key('zabbix-sender-sleep'): sleep = CONF['config']['zabbix-sender-sleep']
  if CONF['config'].has_key('zabbix-sender-random-sleep'): rsleep = int(CONF['config']['zabbix-sender-random-sleep'])
  if CONF['config'].has_key('zabbix-sender-failed-size-limit'): limit = CONF['config']['zabbix-sender-failed-size-limit']

  time.sleep(float(sleep))
  rsleep = random.uniform(0,rsleep)
  time.sleep(rsleep)

  data = {}
  i = 0

  if os.path.exists(path + file) is False:
    _writeSyslog("zabbix-sender=result_file_is_not_found, file=%s" % (path + file))
    return 0

  f = codecs.open(path + file,'r')
  for line in f:
    match = re.search('^#',line)
    if match: continue
    line = line.rstrip()
    splist = re.split(' ',line,3)
    data[i] = {}
    try:
      data[i]['host']  = splist[0]
      data[i]['key']   = splist[1]
      data[i]['clock'] = splist[2]
      data[i]['value'] = splist[3]
      i += 1
    except:
      _writeSyslog("zabbix-sender=format_error, file=%s, data=%s" % (path + file, splist))
  f.close()

  splitdata = 200
  cnt = 0
  sendlist = []

  ret = 0
  for x in range(len(data)):
    sdata = '{'
    for y in ['host', 'key', 'value', 'clock']:
      sdata += '"%s":"%s",' % (y,data[cnt][y])
    sdata = sdata.rstrip(',') + '}'
    sendlist.append(sdata)
    if OPT['VERBOSE']: print "%d: %s" % (x+1,sdata)
    cnt += 1
    if ( cnt % splitdata == 0 ):
      if ret == 0:
        ret += _send_data(server,port,timeout,_pack_data(sendlist))
        time.sleep(sleep + rsleep)
      sendlist = []

  ret += _send_data(server,port,timeout,_pack_data(sendlist))

  if ret > 0 and mode == 0:
    try:
      size = os.path.getsize(path + "failed_" + zabbix + ".result")
      if size > limit:
        _writeSyslog("zabbix-sender=update_failed, file=%s, size=%s, limit=%s" % (path + "failed_" + zabbix + ".result", size, limit))
        return ret
    except:
      pass
    f = codecs.open(path + "failed_" + zabbix + ".result",'a')
    for x in data.keys():
      f.write("%s %s %s %s\n" % (data[x]['host'],data[x]['key'],data[x]['clock'],data[x]['value']))
    f.close()

  return ret

def _send_data(zabbix,port,timeout,msg):
  response_raw = ""

  ### make socket
  socket.setdefaulttimeout(timeout)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  try:
  ### connect to zabbix server
    sock.connect((zabbix, port))
    _writeSyslog("zabbix-sender=connection_success, server=%s, port=%d" % (zabbix,port))

  except:
    sock.close()
    _writeSyslog("zabbix-sender=connection_failed, server=%s, port=%d" % (zabbix,port))
    return 1

  ### send the data to the server
  sock.sendall(msg)
  _writeSyslog("zabbix-sender=send_data, server=%s, port=%d" % (zabbix,port))

  ### read response msg, the first bytes are the header again
  try:
    response_header = sock.recv(5)
  except socket.timeout:
    sock.close()
    _writeSyslog("zabbix-sender=response_failed(timeout1), server=%s, port=%d" % (zabbix,port))
    return 1

  if not response_header == 'ZBXD\1':
    _writeSyslog("zabbix-sender=response_failed, server=%s, port=%d" % (zabbix,port))
  try:
    response_data_header = sock.recv(8)
    response_data_header = response_data_header[:4]
    response_len = struct.unpack('i', response_data_header)[0]
    response_raw = sock.recv(response_len)
  except socket.timeout:
    sock.close()
    _writeSyslog("zabbix-sender=response_failed(timeout2), server=%s, port=%d" % (zabbix,port))
    return 1

  ### check response data
  if re.search('"response":"success",',response_raw):
    s = re.search('processed: (\d+); failed: (\d+);',response_raw)
    _writeSyslog("zabbix-sender=result, server=%s, port=%d, success=%s, failed=%s" % (zabbix,port,s.group(1),s.group(2)))

  sock.close()
  _writeSyslog("zabbix-sender=connection_close, server=%s, port=%d" % (zabbix,port))

  return 0

def _pack_data(listdata):
  msg = '{"request":"sender data","data":['
  for x in listdata:
    msg += "%s," % (x)
  msg = msg.rstrip(',') + ']}'

  data_length = len(msg)
  data_header = struct.pack('i', data_length) + '\0\0\0\0'
  send_data = 'ZBXD\1%s%s' % (data_header,msg)
  return send_data

def _zabbix_servers(servers):
  ret = []
  for x in servers.split(","):
    if re.search("@",x):
      ret.append(x)
    else:
      ret.append(x + "@10051")
  return ret

def la():
  me = sys._getframe().f_code.co_name
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')
  core = 0

  ### count cpu core
  try:
    file = open("/proc/cpuinfo","r")
    try:
      for line in file:
        if re.match('^processor\s+:\s+\d+',line): core += 1
    finally:
      file.close()
  except IOError, (errno, msg):
    pass

  try:
    file = open("/proc/loadavg","r")
    try:
      for line in file:
        m = re.match('^([0-9\.]+)\s([0-9\.]+)\s([0-9\.]+)\s',line)
        for type,num in izip(['avg1','avg5','avg15'],[1,2,3]):
          if m:
            value[me + '.' + type ] = float(m.group(num))
          if core > 0:
            value[me + '.per_cpu.' + type ] = '%.2f' % (value[me + '.' + type ] / core)
    finally:
      file.close()
  except IOError, (errno, msg):
    value[me + '.avg1'] = 0
    value[me + '.avg5'] = 0
    value[me + '.avg15'] = 0

  return value

def mem():
  me = sys._getframe().f_code.co_name
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')

  for item in ['MemTotal','MemFree','Cached','Buffers','Active','Inactive','SwapTotal','SwapFree','Slab']:
    item = me + "." + item
    value[item] = 0

  try:
    file = open("/proc/meminfo","r")
    try:
      for line in file:
        m = re.match('^(\S+):\s+(\d+)\s',line)
        if m:
          item = me + "." + m.group(1)
          if value.has_key(item):
            if int(m.group(2)) > 0:
              value[item] = int(m.group(2)) * 1024
    finally:
      file.close()
  except IOError, (errno, msg):
    pass
  return value

### Receive/Transmit bytes
def net():
  me = sys._getframe().f_code.co_name
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')
  try:
    file = open("/proc/net/dev","r")
    try:
      for line in file:
        m = re.search('([\w\.]+):[\s]*(\d+)\s+(\d+\s+){7}(\d+)',line)
        if m:
          value[me + '.in[' + m.group(1) + ']'] = m.group(2)
          value[me + '.out[' + m.group(1) + ']'] = m.group(4)
    finally:
      file.close()
  except IOError, (errno, msg):
    pass

  return value

def io():
  me = sys._getframe().f_code.co_name
  disk = ""
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')
  items = ['disk','read_requests','read_sectors','write_requests','write_sectors','msec_total']
  try:
    file = open("/proc/diskstats","r")
    try:
      for line in file:
        if re.search('0 0 0 0 0 0 0 0 0 0 0',line): continue
#        m = re.search('([a-z]+[0-9]?)\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+(\d+)\s+',line)
        m = re.search('([a-z]+0?)\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+(\d+)\s+',line)
        if m:
          for item,data in izip(items,m.groups()):
            if item == 'disk':
              key = '[' + data + ']'
            else:
              value[me + '.' + item + key ] = int(data)
          value[me + '.' + 'tput' + key ] = value[me + '.read_requests' + key] + value[me + '.write_requests' + key]
    finally:
      file.close()
  except IOError, (errno, msg):
    pass
  return value

def cpu():
  me = sys._getframe().f_code.co_name
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')
  items = ['user','nice','system','idle','iowait','irq','softirq','steal']
  try:
    file = open("/proc/stat","r")
    try:
      for line in file:
        m = re.match('^cpu\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+',line)
        if m:
          for item,data in izip(items,m.groups()):
            value[me + '.' + item] = int(data)
    finally:
      file.close()
  except IOError, (errno, msg):
    for item in items:
      value[me + '.' + item] = 0
  return value

def _makeData(value):
  host = CONF['config']['hostname']
  list = []
  epoctime = value.pop('epoctime')
  for item in sorted(value.keys()):
    list.append("%s %s %s %s" % (host,item,epoctime,value[item]))
  return list

def _makeDiff(value,stpath):
  epoctime = int(value.pop('epoctime'))
  diff = {}
  diff["epoctime"] = epoctime

  try:
    kind = value.keys()[0].split('.')[0]
  except:
    return diff

  tmpfile = '%s%s.tmp' % (stpath,kind)

  if os.path.exists(tmpfile) is False:
    try:
      file = open(tmpfile,'w')
      try:
        for item in value.keys():
          file.write("%s %s %s\n" % (epoctime, item, value[item]))
      finally:
        file.close()
    except IOError, (errno, msg):
      pass
    for item in value.keys():
      diff[item] = 0
    diff['passdtime'] = 0
  else:
    try:
      old = {}
      file = open(tmpfile,'r+')
      for line in file:
        m = re.match('^(\d+)\s+(\S+)\s+(\S+)$',line)
        if m:
          old['epoctime'] = int(m.group(1))
          old[m.group(2)] = int(m.group(3))
          diff['passdtime'] = epoctime - old['epoctime']
      try:
        file.seek(0)
        for item in value.keys():
          file.write("%s %s %s\n" % (epoctime, item, value[item]))
        file.truncate()
      finally:
        file.close
    except IOError:
      for item in value.keys():
        diff[item] = 0
    for item in value.keys():
      diff[item] = value[item] - old[item]
      if diff[item] < 0: diff[item] = 0

  return diff

def _cpuCalc(value):
  epoctime = int(value.pop('epoctime'))
  passdtime = int(value.pop('passdtime'))
  if passdtime == 0:
    value.clear()
  total = sum(value.values())
  if total > 0:
    for item in value.keys():
      value[item] = '%.2f' % (1.0 * value[item] / total * 100)
  value['epoctime'] = epoctime

  return value

def _ioCalc(value,insector):
  try:
    passdtime = int(value.pop('passdtime'))
  except:
    return value

  ignore = ['msec_total','tput','write_requests','read_requests','write_sectors','read_sectors']
  epoctime = int(value.pop('epoctime'))

  if passdtime == 0:
    value.clear()
  data = {}
  tags = {}
  for key in value.keys():
    m = re.match('^io.\S+(\[[a-z]+0?\])$',key)
    if m: tags[m.group(1)] = True
  for key in tags.keys():
    m = re.match('^\[([a-z]+0?)\]$',key)
    if os.path.exists("/sys/block/%s/queue/physical_block_size" % (m.group(1))):
      file = open("/sys/block/%s/queue/physical_block_size" % (m.group(1)),"r")
      slist = file.readlines()
      file.close()
      sector = slist[0].rstrip()
    else:
      sector = insector
    value['io.read' + key] = '%.2f' % ((1.0 * value['io.read_sectors' + key] * int(sector)) / passdtime)
    value['io.write' + key] = '%.2f' % ((1.0 * value['io.write_sectors' + key] * int(sector)) / passdtime)

    ### requests per sec
    value['io.read_rps' + key] = '%.2f' % ((1.0 * value['io.read_requests' + key] ) / passdtime)
    value['io.write_rps' + key] = '%.2f' % ((1.0 * value['io.write_requests' + key] ) / passdtime)

    if value['io.tput' + key] > 0:
      value['io.svctm' + key] = '%.2f' % (1.0 * value['io.msec_total' + key] / value['io.tput' + key])
    else:
      value['io.svctm' + key] = 0
    ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
    value['io.util' + key] = '%.2f' % (((1.0 * value['io.msec_total' + key] * ticks ) / passdtime ) / 1000)

  for key in tags.keys():
    for item in ignore:
      if value.has_key('io.' + item + key):
        del value['io.' + item + key]

  value['epoctime'] = epoctime
  return value


def _setResource(value,ignore):
  global RESOURCE
  for line in value:
    if re.search(ignore,line.split(" ")[1]): continue
    RESOURCE.append("%s" % (line))

###
def fs():
  me = sys._getframe().f_code.co_name
  value = {}
  value['epoctime'] = datetime.now().strftime('%s')
  path = []
  fs = {
    'vfs':1,
    'ext':1,
    'ext3':1,
    'ext4':1,
    'xfs':1
  }
  try:
    file = open("/proc/1/mounts","r")
    try:
      for line in file:
        m = re.search('^\/\S+\s+(\/[\S]*)\s+(\w+)\s+',line)
        if m:
          if fs.has_key(m.group(2)) is True:
            path.append(m.group(1))

      for mpoint in path:
        st = os.statvfs(mpoint)
        value[me + '.size[' + mpoint + ']']   = st.f_frsize * (st.f_blocks - (st.f_bfree - st.f_bavail))
        value[me + '.free[' + mpoint + ']']  = st.f_frsize * st.f_bavail
        value[me + '.used[' + mpoint + ']']  = st.f_frsize * ((st.f_blocks - (st.f_bfree - st.f_bavail)) - st.f_bavail )
        value[me + '.pfree[' + mpoint + ']'] = "%.2f" % (1.0 * value[me + '.free[' + mpoint + ']'] / value[me + '.size[' + mpoint + ']'] * 100)
        value[me + '.pused[' + mpoint + ']'] = "%.2f" % (1.0 * value[me + '.used[' + mpoint + ']'] / value[me + '.size[' + mpoint + ']'] * 100)

        value[me + '.isize[' + mpoint + ']']   = (st.f_files - (st.f_ffree - st.f_favail))
        value[me + '.ifree[' + mpoint + ']']  = st.f_favail
        value[me + '.iused[' + mpoint + ']']  = ((st.f_files - (st.f_ffree - st.f_favail)) - st.f_favail )
        value[me + '.ipfree[' + mpoint + ']'] = "%.2f" % (1.0 * value[me + '.ifree[' + mpoint + ']'] / value[me + '.isize[' + mpoint + ']'] * 100)
        value[me + '.ipused[' + mpoint + ']'] = "%.2f" % (1.0 * value[me + '.iused[' + mpoint + ']'] / value[me + '.isize[' + mpoint + ']'] * 100)

    finally:
      file.close()
  except IOError, (errno, msg):
    pass

  return value

def _getResource(stpath,ignore):
  sector = 512
  _writeSyslog('kind=resource, ignore="%s"' % (ignore))
  _setResource(_makeData(la()),ignore)
  _setResource(_makeData(mem()),ignore)
  _setResource(_makeData(_cpuCalc(_makeDiff(cpu(),stpath))),ignore)
  _setResource(_makeData(net()),ignore)
  _setResource(_makeData(_ioCalc(_makeDiff(io(),stpath),sector)),ignore)
  _setResource(_makeData(fs()),ignore)

# return True = Change, False = Not Change
def _checkLastData(host,item,newdata):
  if LASTDATA.has_key(host):
    if LASTDATA[host].has_key(item):
      if LASTDATA[host][item] == str(newdata):
        return False
  return True

def _readLastData(path):
  global LASTDATA

  for kind in CONF.keys():
    if kind == 'config': pass

    lastfile = path + kind + '.result'
    if os.path.exists(lastfile):
      for line in codecs.open(lastfile,'r'):
        m = re.match('^(\S+) (\S+) \d+ (\S+)$',line)
        if m:
          (host,item,data) = (m.group(1),m.group(2),m.group(3))
          if LASTDATA.has_key(host) is False: LASTDATA[host] = {}
          LASTDATA[host][item] = data

# PATHの取得
def _checkEnvironment():
  global PATH
  PATH['root'] = os.path.dirname(__file__)
  if PATH['root'] == '': PATH['root'] = '.'
  PATH['status']  = PATH['root'] + '/status/'
  PATH['result']  = PATH['root'] + '/result/'

  for directory in PATH.values():
    if os.path.isdir(directory) is False: os.mkdir(directory)

def _readConfig(conf=''):
  m = re.match('^(\S+)\.\S+$',os.path.basename(__file__))
  json = PATH['root'] + '/' + m.group(1) + '.json'
  yaml = PATH['root'] + '/' + m.group(1) + '.yaml'
  if conf != '':
    if re.match('^https?://\S+$',conf):
      return _readConfigJsonUrl(conf)
    elif os.path.exists(conf) is False:
      sys.stderr.write("%s is not found.\n" % (conf))
      sys.exit(1)
  for file in [conf,json,yaml]:
    if os.path.exists(file):
      if re.search('.json$',file):
        return _readConfigJson(file)
      elif re.search('.yaml$',file):
        if OPT['yaml']: return _readConfigYaml(file)
      else:
        _usage()

# HTTPでのJSONファイルの読み込み=>失敗した時の処理を追加する
def _readConfigJsonUrl(url):
  url = url.replace('$hostname',os.uname()[1])
  savejson = PATH['root'] + '/url.json'
  if ((datetime.now().hour * 60 + datetime.now().minute) % int(OPT['PER-MINUTES']) > 0):
    if os.path.exists(savejson):
      return json.load(codecs.open(savejson,'r'))
  code = "200"
  try:
    jconf = urllib2.urlopen(urllib2.Request(url)).read()
  except urllib2.HTTPError, e:
    code = e.code
  finally:
    if code == "200":
      f = codecs.open(savejson,'w')
      f.write('%s' % (jconf))
      f.close
      return json.loads(jconf)
    elif os.path.exists(savejson):
      return json.load(codecs.open(savejson,'r'))
    else:
      print "config file is not found."
      sys.exit(1)

# YAMLファイルの読み込み
def _readConfigYaml(config):
  return yaml.load(codecs.open(config,'r'))

# JSONファイルの読み込み
def _readConfigJson(config):
  return json.load(codecs.open(config,'r'))

if __name__ == '__main__':
  ### スクリプトパスの調査
  _checkEnvironment()

  _readOption()
  CONF = _readConfig(OPT['CONF'])

  if OPT['SHOW']:
    print json.dumps(CONF, indent=4, separators=(',', ': '))
    sys.exit(0)

  _initConfig()

  if OPT['KIND'] != "":
    _createTmpl(OPT['KIND'],OPT['TVERSION'])
    sys.exit(0)

  CONF['config']['hostname'] = CONF['config'].get('hostname',os.uname()[1])

  if CONF['config'].get('fqdn',True) is True:
    pass
  else:
    CONF['config']['hostname'] = CONF['config']['hostname'].split('.')[0]

  if CONF['config']['syslog']:
    syslog.openlog('logmonitor.py',syslog.LOG_PID,syslog.LOG_DAEMON)

  starttime = datetime.now().strftime('%s')

  if CONF['config'].has_key('zabbix-server') == False:
    CONF['config']['zabbix-server'] = "127.0.0.1@10051"

  if CONF['config']['lock']:
    ret = _lock(PATH['root'] + '/','on')

    if CONF['config']['zabbix-sender']:
      item = "lock"
      if CONF['config'].has_key('lock-item'): item = CONF['config']['lock-item']
      #if os.path.isdir(respath) is False: os.mkdir(respath)
      f = codecs.open(PATH['result'] + "lock.result",'w')
      f.write("%s %s %s %s\n" % (CONF['config']['hostname'],item,starttime,ret))
      f.close()
    if ret == 1:
      for zabbix in _zabbix_servers(CONF['config']['zabbix-server']):
        _zabbix_sender(zabbix,PATH['result'],"lock.result",1)
      sys.stderr.write('Error: Please check syslog\n')
      sys.exit(1)

  _writeSyslog("read=start")

  thread = {}
  if CONF['config']['resource']:
    thread['config'] = threading.Thread(name='config',target=_getResource, args=(PATH['status'],CONF['config']['ignore-resource'],))
    thread['config'].start()
  for kind in CONF.keys():
    if kind == 'config': continue
    if CONF[kind].has_key('per-minutes') is False:
      pass
    elif (datetime.now().hour * 60 + datetime.now().minute) % int(CONF[kind]['per-minutes']) > 0:
      del CONF[kind]
      del RESULT[kind]
      continue
    _readStatus(PATH['status'],kind)

    tcount = 1
    while tcount > 0:
      tcount = 0
      for tkind in CONF.keys():
        if tkind == 'config' and CONF[tkind]['resource'] is False : continue
        try:
          if thread[tkind].isAlive(): tcount += 1
        except:
          pass
      if tcount < CONF['config'].get('max-threads',5):
        thread[kind] = threading.Thread(name=kind,target=_readlog, args=(kind,))
        thread[kind].start()
        tcount = 0
      else:
        time.sleep(0.25)

# thread check
  tend = 1
  while tend > 0:
    tend = 0
    for kind in CONF.keys():
      if kind == 'config' and CONF[kind]['resource'] is False : continue
      if thread[kind].isAlive():
        tend += 1
    time.sleep(0.15)

  _writeSyslog("read=finish")

  _readLastData(PATH['result'])

  for kind in CONF.keys():
    if kind == 'config': continue
    _updateStatus(PATH['status'],kind)

  for kind in CONF.keys():
    _renameResult(PATH['result'],kind)

  _writeSyslog("write=start")
  _result()
  _writeSyslog("write=finish")

  if CONF['config']['lock']:
    if CONF['config']['zabbix-sender']:
      for zabbix in _zabbix_servers(CONF['config']['zabbix-server']):
        _zabbix_sender(zabbix,PATH['result'],"lock.result",1)
    _lock(PATH['root'] + '/','off')

  if CONF['config']['zabbix-sender']:
    for zabbix in _zabbix_servers(CONF['config']['zabbix-server']):
      ret = _zabbix_sender(zabbix,PATH['result'],"all.result",0)
      if os.path.exists(PATH['result'] + "failed_" + zabbix + ".result") and ret == 0:
        ret = _zabbix_sender(zabbix,PATH['result'],"failed_" + zabbix + ".result",1)
        if ret == 0:
          os.remove(PATH['result'] + "failed_" + zabbix + ".result")

  if CONF['config']['syslog']:
    syslog.closelog()

  sys.exit(0)
