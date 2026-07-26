<?php 
   include 'db_connect.php';

   $query = 'SELECT * FROM Course WHERE cid = "' . $_GET['cid'] . '"';
   echo $query;
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }

   echo '<br><br>';
   
   echo '<form action="save_course.php">';
   while($row = mysql_fetch_row($result))
   {
	echo '<input name="cid" type="text" value="'. $row[0] . '"/>';
	echo '<input name="name" type="text" value="'. $row[1] . '"/>';
   }
   echo '<input type="submit"/>';
   echo '</form>';   


   
?>   
