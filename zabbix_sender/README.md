# zabbix_sender

This script is Zabbix_Sender with python

## usage
```
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
```

## how to
```
send data
$ ./zabbix_sender.py -z 127.0.0.1 -s example.net -k trapper[key] -o 100

send server resouce data
$ ./getRes4zbxs.py -o /var/tmp/zabbix_sender.txt -i "fs.i|vda[12]|eth2|per_cpu|boot" -w example.net
$ cat /var/tmp/zabbix_sender.txt
example.net la.avg15 1442052672 0.86
example.net la.avg1 1442052672 0.54
example.net la.avg5 1442052672 0.75
example.net mem.Cached 1442052672 147509248
example.net mem.Buffers 1442052672 0
example.net mem.Inactive 1442052672 403107840
example.net mem.SwapFree 1442052672 963031040
example.net mem.Slab 1442052672 121339904
example.net mem.MemTotal 1442052672 1041502208
example.net mem.SwapTotal 1442052672 2181033984
example.net mem.Active 1442052672 362512384
example.net mem.MemFree 1442052672 83075072
example.net cpu.iowait 1442052672 0.70
example.net cpu.steal 1442052672 0.00
example.net cpu.system 1442052672 9.29
example.net cpu.user 1442052672 8.99
example.net cpu.irq 1442052672 0.00
example.net cpu.nice 1442052672 0.00
example.net cpu.idle 1442052672 80.97
example.net cpu.softirq 1442052672 0.05
example.net net.in[lo] 1442052672 93935043703
example.net net.out[lo] 1442052672 93935043703
example.net net.out[eth1] 1442052672 0
example.net net.in[eth0] 1442052672 68008292768
example.net net.in[eth1] 1442052672 936
example.net net.out[eth0] 1442052672 177646495349
example.net io.read[vda] 1442052672 114688.00
example.net io.write[vda] 1442052672 346060.80
example.net io.util[vda] 1442052672 2.42
example.net io.svctm[vda] 1442052672 0.55
example.net fs.used[/] 1442052672 98678951936
example.net fs.pfree[/] 1442052672 5.67
example.net fs.pused[/] 1442052672 94.33
example.net fs.size[/] 1442052672 104605171712
example.net fs.free[/] 1442052672 5926219776
$ ./zabbix_sender.py -z 127.0.0.1 -d -i /var/tmp/zabbix_sender.txt
```
