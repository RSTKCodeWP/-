<?php 
   include 'db_connect.php';

   $query = "SELECT * FROM User"; 
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
   
   echo '<select id="user_list">';
   echo '<option>--SELECT--</option>';
   while($row = mysql_fetch_row($result))
   {
	$output = '<option value="' . $row[0]. '">' . $row[1] . '</option>';
	echo $output; 
   }
   echo '</select>';
   
?>   
