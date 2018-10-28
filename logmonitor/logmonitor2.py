#!/usr/bin/env python3.4
#-*- coding: utf-8 -*-
#
# Written by  : ma3ki@ma3ki.net
# Version     :
# Create date : Aug 8, 2018
# Last update : 

import os,sys,re,json,codecs,urllib.request,urllib.error,urllib.parse,subprocess,syslog,threading,time,struct,socket,random,collections
#import os,sys,re,json,codecs,urllib,subprocess,syslog,threading,time,struct,socket,random,collections
from datetime import datetime,timedelta

try:
  import yaml
except:
  pass

def _usage():
  print("usage) %s [ -c config-file or url ] [-v] [-s] [-r] [-d]" % (__file__))
  sys.exit(1)

## status と result ディレクトリを作成する
def _setPath():
  path = {}
  path['root'] = os.path.dirname(__file__)
  if path['root'] == '': path['root'] = '.'

  for key in ['status', 'result']:
    path[key] = path['root'] + '/' + key + '/'
    if os.path.isdir(path[key]) is False: os.mkdir(path[key])
  return path

def _readOption():
  # オプションのデフォルト値のセット
  option = {} ;
  for key in ['verbose', 'dry-run', 'show', 'debug']:
    option[key] = 0
  for key in ['conf']:
    option[key] = ''

  # オプションの読み込み
  count = 1
  while count < len(sys.argv):
    if re.match("(-v|--verbose)",sys.argv[count]):
      option['verbose'] = 1
    elif re.match("(-r|--dry-run)",sys.argv[count]):
      option['dry-run'] = 1
    elif re.match("(-s|--show)",sys.argv[count]):
      option['show'] = 1
    elif re.match("(-d|--debug)",sys.argv[count]):
      option['debug'] = 1
    elif re.match("(-c|--conf)",sys.argv[count]):
      count += 1
      try:
        option['conf'] = sys.argv[count]
      except:
        _usage()
    else:
      _usage()
    count += 1
  return option

def _readConfig(path,conf=''):

  # JSON URL の読み込み
  def _readConfigJsonUrl(url):
    url = url.replace('$hostname',os.uname()[1])
    savejson = path['root'] + '/url.json'
    code = "200"
    try:
      jconf = urllib.request.urlopen(urllib.request.Request(url)).read()
    except urllib.error.HTTPError as e:
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
        print("%s file is not found." % savejson)
        sys.exit(1)

  # YAMLファイルの読み込み
  def _readConfigYaml(yconf):
    try:
      return yaml.load(codecs.open(yconf,'r'))
    except:
      print(sys.exc_info())
      sys.stderr.write("yaml.load(%s) error.\n" % (yconf))
      sys.exit(1)

  # JSONファイルの読み込み
  def _readConfigJson(jconf):
    return json.load(codecs.open(jconf,'r'))

  m = re.match('^(\S+)\.\S+$',os.path.basename(__file__))
  path['json'] = path['root'] + '/' + m.group(1) + '.json'
  path['yaml'] = path['root'] + '/' + m.group(1) + '.yaml'

  if conf != '':
    if re.match('^https?://\S+$',conf):
      return _readConfigJsonUrl(conf)
    elif os.path.exists(conf) is False:
      sys.stderr.write("%s is not found.\n" % (conf))
      sys.exit(1)
  for file in [conf,path['json'],path['yaml']]:
    if os.path.exists(file):
      if re.search('.json$',file):
        return _readConfigJson(file)
      elif re.search('.yaml$',file):
        return _readConfigYaml(file)
      else:
        _usage()
  sys.stderr.write("config is not found.\n")
  sys.exit(1)

def _setItems(items,results):
  for kind in list(items.keys()):
    items[kind]['result'] = path['result'] + kind + '.result'
    items[kind]['status'] = path['result'] + kind + '.status'
    for order in list(items[kind].keys()):
      try:
        items[kind][order].keys()
      except:
        continue
      for item in list(items[kind][order].keys()):
        if re.match("(count|uniq_count|sum|average)",order):
          results[kind][order][item] = 0.0
        else:
          results[kind][order][item] = []
        for filters in list(items[kind][order][item].keys()):
          try:
            items[kind][order][item][filters] = re.compile(items[kind][order][item][filters])
          except:
            if filters == 'ignore':
              count = 0
              for ignore in items[kind][order][item][filters]:
                items[kind][order][item][filters][count] = re.compile(ignore)
            continue
      
def _setDefaultConfig():
  defconf = {}
  defconf['config'] = {}
  defconf['config']['syslog']			= False
  defconf['config']['syslog-name']		= 'logmonitor'
  defconf['config']['lock']			= True
  defconf['config']['hostname']			= os.uname()[1]
  defconf['config']['fqdn']			= True
  defconf['config']['resource']			= False
  defconf['config']['generation']		= 10
  defconf['config']['ignore-resource']		= '^$'
  defconf['config']['zabbix-sender']		= False
  defconf['config']['zabbix-server']		= '127.0.0.1'
  defconf['config']['zabbix-server-port']	= '10051'
  defconf['config']['zabbix-timeout']		= 15
  defconf['config']['zabbix-sleep']		= 1
  defconf['config']['zabbix-random-sleep']	= 1
  defconf['config']['zabbix-failed-size-limit']	= 104857600
  defconf['config']['mattermost']			= True
  defconf['config']['mattermost-incoming-webfook']	= ""
  defconf['config']['mattermost-channel']		= ""
  defconf['config']['max-threads']		= 5
  defconf['config']['check-thread-interval']	= 0.2

  return defconf

class AutoVivification(dict):
  """Implementation of perl's autovivification feature."""
  def __getitem__(self, item):
    try:
      return dict.__getitem__(self, item)
    except KeyError:
      value = self[item] = type(self)()
      return value

def _pasttime(starttime):
  pasttime = datetime.now() - starttime
  return pasttime.seconds + float(pasttime.microseconds)/1000000

def _deepUpdate(dict_base, other):
  for k, v in other.items():
    if isinstance(v, collections.Mapping) and k in dict_base:
      _deepUpdate(dict_base[k], v)
    else:
      dict_base[k] = v

def _writeSyslog(output):
    try:
      syslog.syslog(syslog.LOG_INFO,output)
    except:
      syslog.syslog(syslog.LOG_INFO,'syslog output failed')

def _output():
  def _postMattermost(host, kind, order, item, value):
    payload = {}
    payload['text'] = "|host|kind|order|item|value|\n|---|---|---|---|---|\n|" + host + "|" + kind + "|" + order + "|" + item + "|" + value + "|"
    payload['channel']  = config['mattermost-channel']

    encoded_post_data = urllib.parse.urlencode({'payload': json.dumps(payload)}).encode('ascii')
    with urllib.request.urlopen(url=config['mattermost-incoming-webhook'], data=encoded_post_data) as response:
      the_page = response.read()

  def _writeResult(kind,order,output):
    host, item, unixitime, value = output.split(" ",3)

    f = open(items[kind]['result'],'a')
    f.write(output + '\n')
    f.close()

    if config['mattermost']:
      _postMattermost(host, kind, order, item, value)


  for kind in list(results.keys()):
    unixtime = status[kind]['unixtime']
    if 'hostname' in items[kind]:
      hostname = items[kind]['hostname']
    else:
      hostname = config['hostname']
    if config.get('fqdn',False) is True:
      hostname = config['hostname'].split('.')[0]

    for order in sorted(results[kind].keys()):
      for item in sorted(results[kind][order].keys()):
        if order == 'count':
          print("%s %s %s %s" % (hostname,item,unixtime,results[kind][order][item]))
          _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,results[kind][order][item]))
        if order == 'text':
          for line in results[kind][order][item]:
            print("%s %s %s %s" % (hostname,item,unixtime,line))
            _writeResult(kind,order,"%s %s %s %s" % (hostname,item,unixtime,line))
   
def _collection(kind,line):
  global results

  def _count(kind,order,line,s):
    value = ""
    if 'value' in s.groupdict():
      value = s.group('value')
    elif ('value' in s.groupdict()) is False and ('match' in s.groupdict()) is False:
      if len(s.groups()) == 1:
        value = s.group(1)
    results[kind][order][item] += 1
 
  def _text(kind,order,line,s):
    value = ""
    vgroup = []
    if 'value' in s.groupdict():
      vgroup.append(s.group('value'))
      value = vgroup[0]
    elif ('value' in s.groupdict()) is False and ('match' in s.groupdict()) is False:
      for x in range(0,len(s.groups())):
        vgroup.append(s.group(x+1))
      if len(vgroup) > 0: value = vgroup[0]
    if value == "": value = line
    results[kind][order][item].append(value.rstrip())
        
  def _ignore(kind,order,item,line):
    if 'ignore' in items[kind][order][item]:
      for ignore in items[kind][order][item]['ignore']:
        if ignore.search(line):
          return False
    return True

  if __name__  == '__main__':
    if line == "": return
    for order in list(items[kind].keys()):
      if re.match("(count|uniq_count|sum|average|text)",order):
        for item in list(items[kind][order].keys()):
          if _ignore(kind,order,item,line) is False: continue
          s = items[kind][order][item]['filter'].search(line)
          if s:
            if option['verbose'] == 1: print("%s => %s,%s,%s,%s" % (line.split('\n')[0],order,kind,item,s.group(0)))
            if order == 'text': _text(kind,order,line,s)
            if order == 'count': _count(kind,order,line,s)
    return

def _readLog(kind):
  def _command(kind,command):
    if 'env' in items[kind]:
      command = items[kind]['env'] + " " + command

    _writeSyslog("command=start, kind=%s, command=\"%s\"" % (kind,command))

    result = subprocess.getstatusoutput(command)

    if result[0] == 0:
      for line in result[1].split('\n'):
        _collection(kind,line)

  def _openFile(kind,file):
    if os.path.exists(file) is False:
      _writeSyslog("kind=%s, openfile=%s, message=file_is_not_found" % (kind,file))
      return False

    _writeSyslog("openfile=start, kind=%s, openfile=%s" % (kind,file))

    f = codecs.open(file,'r')
    for line in f.readlines():
      _collection(kind,line)
    f.close()

  if __name__ == '__main__':
    if 'file' in items[kind]:
      _openFile(kind,items[kind]['file'])
    if 'command' in items[kind]:
      _command(kind,items[kind]['command'])

if __name__ == '__main__':
  ## 必要なディレクトリの作成、パスの設定
  path = {}
  path = _setPath()

  ## オプションの読み込み
  option = {}
  option = _readOption()

  # 設定の読み込み
  config = {}
  config = _setDefaultConfig()
  _deepUpdate(config,_readConfig(path,option['conf']))

  items = {}
  items  = config['items']
  config = config['config']
  
  if option['debug']:
    for key in [ path, option, config, items ]:
      print(json.dumps(key, indent=4, separators=(',', ': ')))

  results = AutoVivification()
  _setItems(items,results)

  status  = AutoVivification()

  if config['syslog']:
    syslog.openlog(config['syslog-name'],syslog.LOG_PID,syslog.LOG_DAEMON)

  starttime = datetime.now().strftime('%s')

  _writeSyslog("Start")

  # ログの集計開始
  thread = {}
  for kind in list(items.keys()):
    if ('per-minutes' in items[kind]) is False:
      pass
    elif (datetime.now().hour * 60 + datetime.now().minute) % int(items[kind]['per-minutes']) > 0:
      del items[kind]
      continue

    threadcnt = 1
    while threadcnt > 0:
      threadcnt = 0
      for item in list(items.keys()):
        try:
          if thread[item].isAlive(): threadcnt += 1
        except:
          pass
      if threadcnt < config['max-threads']:
        status[kind]['time'] = datetime.now()
        status[kind]['unixtime'] = datetime.now().strftime('%s')
        thread[kind] = threading.Thread(name=kind,target=_readLog, args=(kind,))
        thread[kind].start()
        threadcnt = 0
      else:
        time.sleep(config['check-thread-interval'])
  
  threadend = 1
  while threadend > 0:
    threadend = 0
    for kind in list(items.keys()):
      if thread[kind].isAlive():
        threadend += 1
    time.sleep(0.15)

  _output()

  _writeSyslog("Finish")

