<?php 
   include 'db_connect.php';

   $qid = 30;
   $query = "SELECT * FROM Question WHERE qid = " . $qid;
   
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }

   while($row = mysql_fetch_row($result))
   {
	echo $row[0]; 
	echo ' <button class="show_answer" data-qid="';
	echo $qid; 
	echo '"type="button">Show Answer</button>';
   }
   
?>