<?php

error_reporting(0);

$log  = "/var/log/cloudmessage/cloudmessage.log" ;
$list = "/var/log/cloudmessage/cloudregist.list" ;
$tmp  = "/var/log/cloudmessage/cloudregist.tmp" ;

header('Content-type: text/html; charset=UTF-8');

if ( strcmp($_SERVER["REQUEST_METHOD"],"POST") ) {
  echo("Please POST DATA\n");
  exit(1);
}

echo("Thank you for your access.\n");

$postjson = file_get_contents("php://input");
$obj  = json_decode($postjson);

$group  = $obj->{'group'};
$name   = $obj->{'name'};
$regid  = $obj->{'registrationid'};
$status = $obj->{'status'};

$regline = $group . "," . $name . "," . $regid ;

### logging
$date = date('Y/m/d H:i:s') ;
$ip = $_SERVER["REMOTE_ADDR"] ;
$fp = fopen($log,'a');
fwrite($fp,$date . " srcip=" . $ip . ", group=" . $group . ", name=" . $name . ", registrationID=" . $regid . ", status=" . $status . "\n");
fclose($fp);

### readfile
$cnt = 0;
$arrayline = array() ;

$fp = fopen($list,'r');
while (!feof($fp)) {
  $line = fgets($fp);
  $line = rtrim($line,"\n");  
  
  if (! preg_match("/\S+/", $line)) {
    continue ;
  }

  // not match
  if ( strcmp($line,$regline) ) {
    $arrayline[$cnt] = $line;
    $cnt += 1;
  } else {
    continue;
  }
}
fclose($fp);

if (!strcmp($status,"REGISTRATION")) {
  $arrayline[$cnt] = $regline ;
  $cnt += 1;
}

$fp = fopen("$tmp",'w') ;
foreach ($arrayline as $line) {
  fwrite($fp,$line . "\n");
}
fclose($fp);

copy ($tmp,$list);

?>
