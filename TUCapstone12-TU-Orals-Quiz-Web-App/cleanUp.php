<?php
      include 'db_connect.php';   
      
      function replacequotechars($q, $qid, $a, $cid){
	 //     $qid = "1026";
	   //   $q   = "modified questiions for testing";
	     // $a = "ans answereeee";
	     // $cid = "COS230";
	$qQuery = '
	                 UPDATE Question
		         SET question = "'.$q.'"
		        WHERE qid =    "'.$qid.'"
							     
		         ';
									   
			       $result = mysql_query($qQuery);
				           $error =  mysql_error();
			 if($error){
			    die('Error in query: ' . $error);
		           }
													    
	   $AQuery = '
	          UPDATE Answer
	           SET answer = "'.$a.'"
	           WHERE qid =    "'.$qid.'"
	           AND   cid =    "'.$cid.'"
				        
	          ';
															     
	       $result = mysql_query($AQuery);
	       $error =  mysql_error();
	       if($error){
		      die('Error in query: ' . $error);
		      }

      }

             
	      $query = '
	      SELECT DISTINCT q.qid, a.cid , q.question, a.answer FROM Question q
                   INNER JOIN Answer a ON a.qid = q.qid
                   INNER JOIN Course c ON c.cid = a.cid
                  WHERE 1 =1
							                
              ';
							        
	     $result = mysql_query($query);
          $error =  mysql_error();
       if($error){
               die('Error in query: ' . $error);
	      }
															            
          $quoteMark = array('"');
      while($row = mysql_fetch_row($result))
          {
             $question = str_replace($quoteMark, "", $row[2]);
              $answer   = str_replace($quoteMark, "", $row[3]);
              $answer   = str_replace('\n', "", $answer);
	  replacequotechars($question, $row[0], $answer,  $row[1]);
    }
	echo "all done!";
?>
