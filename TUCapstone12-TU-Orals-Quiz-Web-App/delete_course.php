<?php 
	session_start(); 
	include 'db_connect.php'; 

	$cid = $_GET['cid'];

	$query = "DELETE FROM Course
	       	  WHERE CID='" . $cid . "'"; 

	echo $query;

	$result = mysql_query($query);
   	$error =  mysql_error();
   	if($error){
		die('Error in query: ' . $error);
	}
	header( 'Location: courses.php' ) ;
 ?>