<?php 
   include 'db_connect.php';
       echo ' <script type="text/javascript" src="jquery.js"> </script>
	 <script type="text/javascript" src="js.js"> </script>';

   $query = 'SELECT * FROM Question WHERE qid = "' . $_GET['qid'] . '"';
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }

  print '<a href="displayQuestion.php">Back to Modify Questions</a>';

   echo '<br><br>';
      
   while($row = mysql_fetch_row($result))
   {
	echo '<input ID="currQuestion" qid="'. $row[1].'" type="text" value="'. $row[0] . '"/>';
   }

   
	echo "<button  onclick='saveQuestionChanges()' type='button'>Save</button>";
   echo "<div class='responseDiv'></div>";

   echo $query;
?>   
