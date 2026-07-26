<?php 
   include 'db_connect.php';

if(!($_POST["courseid"])) return;
 
function getlistOfquestionsForCourse($acourse)
{
$cid =$acourse;

   $query = 'SELECT DISTINCT q.qid, a.cid , q.question, a.answer FROM Question q
   	     INNER JOIN Answer a ON a.qid = q.qid
	     INNER JOIN Course c ON c.cid = a.cid
	     WHERE 1 =1 
	     '.($cid? 'AND c.cid = "'.$cid.'"':'').'
	     ;
	     ';

   $result = mysql_query($query);
   $error =  mysql_error();
   if($error){
	die('Error in query: ' . $error);
   }
    $json ="[";;
    $quoteMark = array('"');
   while($row = mysql_fetch_row($result))
   {
        $question = str_replace($quoteMark, "", $row[2]);
        $answer   = str_replace($quoteMark, "", $row[3]);
        $answer   = str_replace('\n', "", $answer);
	$json .= '{"QID":"'.$row[0].'","CID":"'.$row[1].'", "question":"'.$question.'", "answer":"'.$answer.'"}  ,';
   }
    $json = substr($json, 0, -1);  
   if($json == ""){

	$json = '[{"QID":"111111","CID":"111111", "question":"Nada silch nothing yet!", "answer":"No questions have been answered for this course yet! go get busy!"}]';
	   echo $json;

		return;
	   }

    $json .= "]";
   echo $json;
   return;
}
      
   getlistOfquestionsForCourse($_POST["courseid"]);
?>   
