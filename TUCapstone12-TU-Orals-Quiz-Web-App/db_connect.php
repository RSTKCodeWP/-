<?php 
   $username = "paulnurkkala";
   $password = "7e7s6y0k";
   $hostname = "sql09.freemysql.net";
   $database = "tucapstone12";

   $connection = mysql_connect($hostname,$username,$password);
   mysql_select_db($database, $connection);
   if(!$connection)
   {
       die('Could not connect: ' . mysql_error());
   }
   else{
   }
?>