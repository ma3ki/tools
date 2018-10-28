<?php

error_reporting(0);
$log = "/var/log/cloudmessage/cloudreply.log" ;

header('Content-type: text/html; charset=UTF-8');

if ( strcmp($_SERVER["REQUEST_METHOD"],"POST") ) {
  echo("Please POST DATA\n");
  exit(1);
}

echo("Thank you for your access.\n");

$postjson = file_get_contents("php://input");
$obj  = json_decode($postjson);

$alertid = $obj->{'alertid'};
$regid   = $obj->{'registrationid'};
$status  = $obj->{'status'};

$input = "" ;
if ( ! strcmp($alertid,"")) {
  $input = $status ;
} else {
  $input = $status . ":" . $alertid ;
}

$m = new Memcached();
$m->addServer("127.0.0.1",11211) or die ("Can't connect memcached");
$m->set($regid, $input);
$value = $m->get($regid);

$date = date('Y/m/d H:i:s') ;
$ip = $_SERVER["REMOTE_ADDR"] ;
$fp = fopen($log,"a");
fwrite($fp,$date . " srcip=" . $ip . ", registrationID=" . $regid . ", status=" . $input . "\n");
fclose($fp);
?>
