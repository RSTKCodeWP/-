<?php 
   session_start();
   include 'db_connect.php';

   $query = "SELECT answer FROM Answer WHERE qid=" . $qid;

   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
   
   if(!isset($result))
   { 
        echo "This question doesn't appear to be answered, yet.";
   }
   
   while($row = mysql_fetch_row($result))
   {
    	echo $row[0];
   }  

?>