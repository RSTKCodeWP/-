<?php 
   include 'db_connect.php';

   
   $query = "INSERT INTO User VALUES (0, '')";
   $result = mysql_query($query);
   $error =  mysql_error();

   	$username = 'paul'; 
	$password = 'password'; 

	$query = "INSERT INTO User VALUES(0,'";
	$query .= $username;
	$query .= "', '"; 
	$query .= $password;
	$query .= "')";

	echo $query;

	$result = mysql_query($query);
   	$error =  mysql_error();
   	if($error){
		die('Error in query: ' . $error);
	}

	if($error){
		die('Error in query: ' . $error);
	}

        var_dump($result);

?>   
