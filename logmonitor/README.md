# logmonitor.py

## 用途
Zabbixへログの集計結果を送信するスクリプト。
ログ、ファイル、コマンドの出力結果を正規表現のfilterで集計し、Zabbix-Sender形式で保存し、かつ、Zabbix-Serverにデータを送信するスクリプト。ログは毎回差分を読み込む。ファイル、コマンドの結果は全てを読み込む。

## 集計機能
|機能名|機能|
|----|----|
|count|filterとmatchした行数|
|sum|filterとmatchした値の合計値|
|average|filterとmatchした値の平均値|
|uniq_count|filterとmatchしたfieldのuniq数|
|geoip_count|filterとmatchしたIPv4アドレスを国毎に集計したリスト|
|text|マッチした行全て(集計ではない)|

# 基本動作設定
|項目|説明|default|
|---|---|---|
|hostname|Zabbixに登録しているホスト名を指定|ホスト名|
|generation|出力結果の保存世代数|10|
|syslog|syslogへの出力(on/off)|off|
|lock|スクリプトの多重起動防止(on/off)|off|
|lock-item|多重起動監視用アイテム名|lock|
|zabbix-sender|zabbixへのデータ送信(on/off)|off|
|zabbix-server|zabbixサーバ(server1,server2...)|127.0.0.1@10051|
|zabbix-sender-timeout|zabbixサーバへの接続タイムアウト秒|5|
|zabbix-sender-sleep|zabbix-sender前に挿入されるsleep時間|1.0|
|zabbix-sender-random-sleep|上記sleepとは別に挿入される最大sleep時間|1|
|zabbix-sender-failed-size-limit|zabbix-sender失敗時に保存される未送信データの最大サイズ|10000000|
|resource|リソースデータ取得(on/off)|off|
|ignore-resource|無視するリソースを正規表現で指定|^$|

基本設定例(設定フォーマットはyaml)
```logmonitor.yaml
$ vi logmonitor.yaml
--------------------------------------------
config:
  hostname: example.net
  generation: 5
  syslog: on
  lock: on
  lock-item: lock
  zabbix-sender: on
  zabbix-server: 127.0.0.1
  zabbix-sender-timeout: 5
  zabbix-sender-sleep: 5
  zabbix-sender-random-sleep: 1
  zabbix-sender-failed-size-limit: 1000000
--------------------------------------------
```

# 集計設定
## 1. count設定例
1-1. nginxのGET,POST数をカウントする
```
$ vi logmonitor.yaml
----- logmonitor.yaml に追記する---------------
nginxAccessLog:
  log: /var/log/nginx/access.log
  rotation: /var/log/nginx/access.log.%Y%m%d
  hostname: example.net
  count:
    nginxGetCount:
      filter: ' "GET '
    nginxPostCount:
      filter: ' "POST '
---------------------------------------------
$ ./logmonitor.py
$ cat result/nginxAccessLog.result
example.net nginxGetCount 1442898242 356
example.net nginxPostCount 1442898242 160
```

1-2. nginxのGET,POST数をカウントする(特定のIPからのアクセスは無視する)
```
$ vi logmonitor.yaml
--------------------------------------------
nginxAccessLog:
  log: /var/log/nginx/access.log
  rotation: /var/log/nginx/access.log.%Y%m%d
  hostname: example.net
  count:
    nginxGetCount:
      filter: ' "GET '
      ignore:
        - '^133.242.186.90'
        - '^2401:2500:102:1114:133:242:186:90'
    nginxPostCount:
      filter: ' "POST '
        - '^133.242.186.90'
        - '^2401:2500:102:1114:133:242:186:90'
---------------------------------------------
$ ./logmonitor.py
$ cat result/nginxAccessLog.result
example.net nginxGetCount 1442898685 130
example.net nginxPostCount 1442898685 160
```

1-3. bind の 問い合わせの多いクエリーと問い合わせ元の上位を集計する
```
$ vi logmonitor.yaml
--------------------------------------------
querylog:
  log: /var/log/namedlog
  hostname: example.net
  count:
    clientIPs:
      display: list
      top: 3
      filter: 'queries: client (¥S+)#¥d+ .* query: ¥S+ IN'
      others: off
    topQueries:
      display: list
      filter: 'queries: client .* query: (¥S+) IN'
---------------------------------------------
$ ./logmonitor.py
$ cat result/querylog.result
example.net clientIPs 1442899343 127.0.0.1=29959
example.net clientIPs 1442899343 2401:2500:102:1114:133:242:186:90=421
example.net clientIPs 1442899343 69.25.139.132=96
example.net topQueries 1442899343 www.yahoo.co.jp=8256
example.net topQueries 1442899343 yahoo.co.jp=4120
example.net topQueries 1442899343 status.aws.amazon.com=1848
example.net topQueries 1442899343 rss.rssad.jp=928
example.net topQueries 1442899343 feeds.feedburner.com=922
example.net topQueries 1442899343 feedblog.ameba.jp=696
example.net topQueries 1442899343 90.186.242.133.in-addr.arpa=610
example.net topQueries 1442899343 ma3ki.net=597
example.net topQueries 1442899343 api.dropbox.com=488
example.net topQueries 1442899343 d.hatena.ne.jp=464
example.net topQueries 1442899343 Others=12439
```

1-4. shellの実行結果とfileからprocessor数をそれぞれ集計する
```
$ vi logmonitor.yaml
--------------------------------------------
cmdCpuCount:
  hostname: example1.net
  command: 'cat /proc/cpuinfo'
  count:
    cpuCount1:
      filter: '^processor'
fileCpuCount:
  hostname: example2.net
  file: '/proc/cpuinfo'
  count:
    cpuCount2:
      filter: '^processor'
---------------------------------------------
$ ./logmonitor.py
$ cat result/cmdCpuCount.result result/fileCpuCount.result 
example1.net cpuCount1 1442903436 2
example2.net cpuCount2 1442903436 2
```

## 2. sum,average 設定例
2-1. postfixのログから配送が成功したメールのサイズ合計値と平均値を取得する
```
$ vi logmonitor.yaml
--------------------------------------------
postfixlog:
  hostname: example.net
  log: /var/log/maillog
  count:
    sendCount:
      filter: ' postfix¥S+: ¥S+: to=.*, status=sent'
  sum:
    sendSizeTotal:
      filter: ' postfix¥S+: (?P<match>¥S+): from=.*, size=(?P<value>¥d+),'
      after: ' postfix¥S+: (?P<match>¥S+): to=.*, status=sent'
  average:
    sendSizeAverage:
      filter: ' postfix¥S+: (?P<match>¥S+): from=.*, size=(?P<value>¥d+),'
      after: ' postfix¥S+: (?P<match>¥S+): to=.*, status=sent'
---------------------------------------------
$ ./logmonitor.py
$ cat result/postfixlog.result
example.net sendSizeAverage 1442905036 138497.07
example.net sendCount 1442905036 14
example.net sendSizeTotal 1442905036 1938959

match と value は filter行でしか使用できない。
value は 数字のみ集計可能
```

2-2. 平均値を整数で出力する
```
$ vi logmonitor.yaml
--------------------------------------------
postfixlog:
  hostname: example.net
  log: /var/log/maillog
  average:
    sendSizeAverage:
      type: integer
      filter: ' postfix¥S+: (?P<match>¥S+): from=.*, size=(?P<value>¥d+),'
      after: ' postfix¥S+: (?P<match>¥S+): to=.*, status=sent'

---------------------------------------------
$ ./logmonitor.py
$ cat result/postfixlog.result
example.net sendSizeAverage 1442905276 138497
```

## 3. uniq_count 設定例
3-1. sendmailのログからユニークなFromアドレス数をカウントする
```
$ vi logmonitor.yaml
--------------------------------------------
maillog:
  hostname: example.net
  log: /var/log/maillog
  uniq_count:
    uniqFromCount:
      filter: ' sendmail¥S+: ¥S+: from=¥S+@(¥S+)>, '
  count:
    FromCount:
      filter: ' sendmail¥S+: ¥S+: from=¥S+@¥S+>, '
---------------------------------------------
$ ./logmonitor.py
$ cat result/postfixlog.result
example.net FromCount 1442905698 128
example.net uniqFromCount 1442905698 40
```

## 4. geoip_count 設定例
4-1. bind の querylog への問い合わせ元を国別に集計する
```
$ vi logmonitor.yaml
--------------------------------------------
querylog:
  hostname: example.net
  log: /var/log/namedlog
  rotation: /var/log/rotation/namedlog-%Y%m%d
  geoip_count:
    countryCode1:
      top: 5
      display: list
      others: off
      filter: 'queries: client (?P<code>(¥d+¥.){3}¥d+)#¥d+ .* query: ¥S+ IN'
      ignore:
        - '127.0.0.1'
    countryCode2:
      display: US,JP
      others: off
      filter: 'queries: client (?P<code>(¥d+¥.){3}¥d+)#¥d+ .* query: ¥S+ IN'
      ignore:
        - '127.0.0.1'
---------------------------------------------
$ ./logmonitor.py
$ cat result/postfixlog.result
example.net countryCode1 1442906550 US=614
example.net countryCode1 1442906550 JP=212
example.net countryCode1 1442906550 NL=10
example.net countryCode1 1442906550 CA=10
example.net countryCode1 1442906550 None=10
example.net countryCode2[US] 1442906550 614
example.net countryCode2[JP] 1442906550 212

display: 国1,国2,... は geoip_countのみで指定可能
```

### ログ集計設定
|項目1|項目2|型|初期値|内容|捕捉|
|---|---|---|---|---|---|
|任意||dict||||
|任意|hostname|文字列|ホスト名|出力内容のホスト名を指定|上記hostnameを上書き|
|任意|log|文字列|ログファイルパス|strftime形式||
|任意|rotation|文字列|ログローテーション時のファイル名|strftime形式||
|任意|rotation-time|-¥d+[dhms]|ログローテーション時のstrftime形式で指定する時間||
|任意|per-minutes|数字|現在の時刻がこの値で割り切れれば実行する||
|任意|file|文字列|ファイルパス|||
|任意|command|文字列|実行コマンド|||
|任意|count|dict|行数|||
|任意|average|dict|平均値|||
|任意|sum|dict|合計値|||
|任意|uniq_count|dict|ユニーク行数|||
|任意|geoip_count|dict|国別行数|||

|項目4|対応項目2|要不要|
|---|---|---|
|filter|全て|必須|
|before/after|count/average/sum/uniq_count|任意(listデータはvalueへ設定できない)|
|display: list|count/geoip_count|geoip_countではdefault|
|display: 値指定|geoip_count|任意|
|display: value|count/average/sum/uniq_count|default|
|top|count/geoip_count|任意|
|others|count/geoip_count|任意|
|calc|sum/average|任意|
|type|全て|任意|
|max-limit|全て|任意|
|min-limit|全て|任意|
|max-limit-over-exec|全て|任意|
|min-limit-over-exec|全て|任意|
|ignore|全て|任意|

