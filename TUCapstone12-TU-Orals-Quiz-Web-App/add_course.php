<?php 
   include 'db_connect.php';
   $query = "INSERT INTO Course VALUES ('COS121', 'Introduction to Computer Science II')";
   $result = mysql_query($query);
   $error =  mysql_error();

   if($error){
	die('Error in query: ' . $error);
   }

   var_dump($result);

?>   
