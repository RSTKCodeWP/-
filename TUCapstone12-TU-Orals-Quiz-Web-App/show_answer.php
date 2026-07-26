<?php 
   include 'db_connect.php';

   echo $_GET['qid'];

   $query = "SELECT * FROM Course";
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
   
   while($row = mysql_fetch_row($result))
   {
   }

?>