#!/usr/bin/python
# -*- encoding: utf-8 -*-
#
# created by ma3ki@ma3ki.net
#
# easy_install python-memcached
#
# usage ) ./cloudmessage.py <GROUP> <TITLE> <MESSAGE>

### import module
import os,sys,random,time,datetime,re
import memcache,json,pycurl,cStringIO,urllib

APIKEY="Set Your API KEY"

LIST = "/var/log/cloudmessage/cloudregist.list"
LOG  = "/var/log/cloudmessage/cloudmessage.log"

TIMEOUT=60
RETRY=3

### fallback email setting
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email import charset
SMTPSERVER = "127.0.0.1"
FROM = "Set From Address"
RCPT = "Set To Address"

RID = []
NAME = {}

def _googlepush(apikey, msg):

  response = cStringIO.StringIO()

  c = pycurl.Curl()
  c.setopt(c.URL, "https://android.googleapis.com/gcm/send")
  c.setopt(c.POST, 1)
  c.setopt(c.CONNECTTIMEOUT, 10)
  c.setopt(c.TIMEOUT, 15)
  c.setopt(c.HTTPHEADER, ["Authorization:key=" + apikey, "Content-Type:application/json"])
  msg['data']['sendtime'] = int(time.time())
  postdata = json.dumps(msg)
  c.setopt(c.POSTFIELDS, postdata)
  c.setopt(c.WRITEFUNCTION, response.write)
  c.perform()
  c.close()

  _writelog(response.getvalue().rstrip())

def _getdate():
  d = datetime.datetime.today()
  date = '%d/%02d/%02d %02d:%02d:%02d' % (d.year,d.month,d.day,d.hour,d.minute,d.second)
  return date

def _gettime():
  d = datetime.datetime.today()
  date = '%02d:%02d:%02d' % (d.hour,d.minute,d.second)
  return date

def _writelog(msg):
  date = _getdate()
  fw = open(LOG,"a")
  fw.write(date + " msg=" + str(msg) + "\n")
  fw.close()

if __name__ == '__main__':

  GROUP   = str(sys.argv[1])
  SUBJECT = str(sys.argv[2])
  MESSAGE = str(sys.argv[3])

  ## check registration user list
  if os.path.exists(LIST):
    for line in open(LIST,'r'):
      if urllib.unquote(line.split(",")[0]) == GROUP:
        uname = urllib.unquote(line.split(",")[1])
        regid = line.split(",")[2].rstrip()
        NAME[regid] = urllib.unquote(uname)
        RID.append(regid)
  else:
    sys.exit(1)

  d = datetime.datetime.today()
  date = '%d/%02d/%02d %02d:%02d:%02d' % (d.year,d.month,d.day,d.hour,d.minute,d.second)
  uniq = '%d%02d%02d%02d%02d%02d-%02d' % (d.year,d.month,d.day,d.hour,d.minute,d.second,random.randint(1,99))

  M = {}
  M['data'] = {}
  M['data']['message']   = urllib.quote(MESSAGE)
  M['collapse_key'] = "CloudMessage"
  M['time_to_live'] = 3600
  M['delay_while_idle'] = False
  
  okflag = False
  ngflag = False
  okid = ""

  ### memcache connect
  memclient = memcache.Client(['127.0.0.1:11211'], debug=1)
  if len(memclient.get_stats() ) == 0:
    raise Exception('memcache server is not connected.')

  ### memcache reset
  for regid in RID:
    memclient.set(str(regid),"")

  ### if message is recovery message
  m = re.search("Recovery",SUBJECT)
  if m:
    M['registration_ids'] = RID[:]
    M['data']['subject']  = urllib.quote(SUBJECT)
    M['data']['alert']    = "false"
    M['data']['timeout']  = "0"
    M['data']['alertid']  = ""
    M['data']['color']    = "green"
    _writelog(M)
    _googlepush(APIKEY,M)
    sys.exit(0)

  ### infomation message for other id
  M['registration_ids'] = RID[:]
  del M['registration_ids'][0]
  M['data']['replyUrl'] = "https://ma3ki.net/php/cloudreply.php"
  if len(M['registration_ids']) > 0:
    M['data']['sound']    = ""
    M['data']['subject']  = urllib.quote("The alert issued.")
    M['data']['alertid']  = ""
    M['data']['timeout']  = "0"
    M['data']['alert']    = "false"
    M['data']['color']    = "yellow"
    _writelog(M)
    _googlepush(APIKEY,M)

  ### main message
  M['data']['subject']  = urllib.quote(SUBJECT)
  M['data']['alertid']  = str(uniq)
  M['data']['timeout']  = str(TIMEOUT)
  M['data']['alert']    = "true"
  M['data']['color']    = "red"
#  M['data']['alarmMusicUrl'] = "http://your music url.mp3";
    
  ### main
  num = 0
  for i in range(RETRY):
    for regid1 in RID:
      M['registration_ids'] = [regid1]
      M['data']['sound']    = str(i+1)

      ### message push
      _writelog(M)
      memclient.set(str(regid1),"")
      _googlepush(APIKEY,M)

      ### wait
      cnt = 0
      rcv = 0
      num += 1
      while cnt < TIMEOUT + 2:
        time.sleep(1)
        value = memclient.get(regid1)
        if not value:
          for regid2 in RID:
            value = memclient.get(regid2)
            if not value:
              pass
            else:
              m = re.match("^(\w+):(\S+)",value)
              if m:
                if m.group(1) == 'OK' and m.group(2) == M['data']['alertid']:
                  M['data']['message'] += urllib.quote('\n %d. %s %s\n' % (num,_gettime(),NAME[regid2]))
                  M['data']['message']   += urllib.quote('   Reply: OK')
                  okflag = True
                  okid = regid2
                  break
        else:
          m = re.match("^(\w+):(\S+)",value)
          if m:
            if m.group(1) == 'RECEIVED' and m.group(2) == M['data']['alertid'] and rcv == 0:
              cnt = 0
              rcv = 1
            else:
              if re.match("(NG|OK)",m.group(1)) and m.group(2) == M['data']['alertid']:
                if num == 1:
                  M['data']['message'] += urllib.quote('\n\n-- Contact History --')
                M['data']['message'] += urllib.quote('\n %d. %s %s\n' % (num,_gettime(),NAME[regid1]))
                if rcv == 1:
                  M['data']['message'] += urllib.quote('   AutoReply: RECEIVED\n')
              if m.group(1) == 'NG' and m.group(2) == M['data']['alertid']:
                cnt = TIMEOUT + 2
                M['data']['message']   += urllib.quote('   Reply: NG')
                ngflag = True
              elif m.group(1) == 'OK' and m.group(2) == M['data']['alertid']:
                M['data']['message']   += urllib.quote('   Reply: OK')
                okflag = True
                okid = regid1
                break
        if okflag:
          break
        cnt += 1
      if okflag:
        break
      if ngflag:
        ngflag = False
      else:
        if num == 1:
          M['data']['message'] += urllib.quote('\n\n-- Contact History --')
        M['data']['message'] += urllib.quote('\n %d. %s %s\n' % (num,_gettime(),NAME[regid1]))
        if rcv == 1:
          M['data']['message'] += urllib.quote('   AutoReply: RECEIVED\n')
        else:
          M['data']['message'] += urllib.quote('   AutoReply: TIMEOUT\n')
        M['data']['message']   += urllib.quote('   Reply: TIMEOUT')
    if okflag:
      break

  M['data']['message'] += urllib.quote('\n---------------------\n')
  M['data']['message']  += urllib.quote('\nPowered by CloudMessage.\n')
  ####### ok
  if okflag :
    for regid in RID:
      M['registration_ids'] = [regid]
      M['data']['sound']    = ""
      M['data']['alert']    = "false"
      M['data']['timeout']  = "0"
      M['data']['subject']  = urllib.quote(NAME[okid] + ' pushed OK button.')
      M['data']['color']    = "white"

      _writelog(M)
      _googlepush(APIKEY,M)
  ####### ng
  else:
    for regid in RID:
      M['registration_ids'] = [regid]
      M['data']['sound']    = "4"
      M['data']['alert']    = "true"
      M['data']['timeout']  = "8"
      M['data']['subject']  = urllib.quote('Nobody was caught.')
      M['data']['color']    = "red"

      _writelog(M)
      _googlepush(APIKEY,M)

    #### fallback email
    message = MIMEText(MESSAGE, 'plain', 'utf-8')
    message['Subject'] = Header(SUBJECT, 'utf-8')
    message['From']    = FROM
    message['To']      = RCPT
    SMTP = smtplib.SMTP(SMTPSERVER)
    SMTP.sendmail(FROM,[RCPT],message.as_string())
    SMTP.close()
