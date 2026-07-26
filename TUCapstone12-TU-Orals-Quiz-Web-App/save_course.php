<?php 
	session_start(); 

	include 'db_connect.php'; 

	$courseID = $_POST["course"];
	$userID   = $_POST["userID"];
	$selected = $_POST["selected"];

	if($selected == "true"){
		 $iQuery = '
   	    		INSERT INTO UserCourse (uid, cid) VALUES('.$userID.' ,"'.$courseID.'")
	     ';

   $result = mysql_query($iQuery);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }

	}else{
		 $qQuery = '
		 		DELETE FROM UserCourse
				WHERE uid = '.$userID.'
				AND   cid = "'.$courseID.'"
	    		 ';

   		 $result = mysql_query($qQuery);
  		 $error =  mysql_error();
 		  if($error){
			die('Error in query: ' . $error);
   		}

	}


	
 ?>
