<?php 
   include 'db_connect.php';
/*
if(!($_POST["courseid"])) return;
 UPDATE table_name
 SET column1=value, column2=value2,...
 WHERE some_column=some_value
*/
   $qQuery = '
   		UPDATE Question
		SET question = "'.$_POST["Question"].'"
		WHERE qid =    "'.$_POST["QID"].'"
   	    	
	     ';

   $result = mysql_query($qQuery);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }

  $AQuery = '
   		UPDATE Answer
		SET answer = "'.$_POST["Answer"].'"
		WHERE qid =    "'.$_POST["QID"].'"
		AND   cid =    "'.$_POST["CID"].'"
   	    	
	     ';

   $result = mysql_query($AQuery);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
  
      
?>   
