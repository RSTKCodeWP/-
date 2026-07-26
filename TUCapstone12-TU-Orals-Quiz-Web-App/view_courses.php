<?php 
   include 'db_connect.php';
     session_start();
 
		   if(!$_SESSION['user_id']){echo "You must log in first!"; return;}
   $query = "
   SELECT DISTINCT C.cid, C.name, UC.uid
   FROM Course C
   LEFT JOIN UserCourse UC ON (UC.uid =".$_SESSION['user_id']." AND UC.cid = C.cid)
             
   ";
   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
  
   echo '<table class="course_table">';
   $checked;
   while($row = mysql_fetch_row($result))
   {
        $checked = $row[2];
	echo '<tr>'; 
	echo '<td><input '.($checked?"checked='checked'":"").'  user="'.$_SESSION['user_id'].'" onclick="saveUserCourse(this);" type="checkbox" class="userCourse" value="'.$row[0].'"  /></td>';
	echo '<td>';	
	echo $row[0];
	echo '</td>';	
	echo '<td>';	
	echo $row[1];
	echo '</td>';
	echo '<td>'; 
	echo '<a href="edit_course.php?cid=' . $row[0] . ' ">Edit</a> ||';
	echo '</td>';	
	echo '<td>'; 
	echo '<a href="delete_course.php?cid=' . $row[0] . ' ">Delete</a>';
	echo '</td>';
   }
   echo '</table>';

   
?>   
