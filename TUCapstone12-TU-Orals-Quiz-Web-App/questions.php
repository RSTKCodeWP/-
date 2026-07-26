<?php 
      session_start();
      include 'db_connect.php';
      include 'displayQuestion.php';
?>
<html>
	<head>
		<title>TU Capstone Study 2012</title>
		<script type="text/javascript" src="jquery.js"> </script>
		<script type="text/javascript" src="js.js"> </script>
		<script type="text/javascript" src="bootstrap/js/bootstrap.js"> </script>
		<link rel="stylesheet" type="text/css" href="css.css" />
		<link rel="stylesheet" type="text/css" href="bootstrap/css/bootstrap.min.css" />
		<link href="bootstrap/css/bootstrap.css" rel="stylesheet">
		    <style type="text/css">
		          body {
				  padding-bottom: 40px;
			       }
			 .sidebar-nav {
		                  padding: 9px 0;
	                       }
			 .sidebarpersonalized{
				  height: 400px !important;
				  overflow: scroll;
				  overflow-x: hidden;
			        }

		          .main{
		               height: 290px !important;
		               overflow: scroll;
		               overflow-x: hidden;
		               }
		          .editQuestion{
	                       float: right;
		               color: gray;

         		        }
			.toogleAnswer{
				float: left;
				color:gray;
				
				}
			.nada{
				color:red;
				background-color:#CCCCCC;
			     }
              	    </style>
		   <link href="bootstrap/css/bootstrap-responsive.css" rel="stylesheet">
</head>

<body>
	<div class="container">
		     <!-- Navbar --> 
		     <div class="navbar">
			<div class="navbar-inner">
			    <a class="brand" href="index.php">TU Capstone Study 2012</a>
			    <ul class="nav">
			      <li><a href="index.php">Home (<?php echo $_SESSION['user'] ?>) </a></li>
			      <li class="dropdown">
			  <a data-toggle="dropdown" class="dropdown-toggle" href="questions.php">Questions 
				<b class="caret"></b></a>
                               <ul class="dropdown-menu">	
			          <li><a onclick="toogleAnswer()" >Toogle Answers</a></li>
	                          <li><a onclick="showModalEdit()">Edit curent Q&A</a></li>
				</ul>
		            	</li>
			      <li><a href="courses.php">Courses</a></li>
			      <li><a href="logout.php">Logout</a></li>
			    </ul>
			    
	     <!-- End Navbar --> 
			   
			</div>
		     </div>
	     <!-- End Navbar --> 


	       <div class="container-fluid">
      <div class="row-fluid">
        <div class="span3 sidebarpersonalized">
          <div class="well sidebar-nav">
            <ul class="nav nav-list">
 		<li class="nav-header">Course List</li>
              
		<?php
		 
		   if(!$_SESSION['user_id']){echo "Please log in"; return;} 
		   $query = 'SELECT DISTINCT C.cid, C.name  FROM Course C
		   	     INNER JOIN UserCourse UC ON UC.cid = C.cid
			     WHERE UC.uid = '.$_SESSION["user_id"].''
			     ;
		   $result = mysql_query($query);
		   $error =  mysql_error();
		   if($error){
			die('Error in query: ' . $error);
		   }
		   
		  $first = true;
		  
		   while($row = mysql_fetch_row($result))
		   {
			if($first){
				$output =  '<li id ="'.$row[0].'" class="active" > <a class = "firstCourse" onclick="getandParseJson(this);" id = "'.$row[0].'">'.$row[1].'</a></li>';
				$first = false;
			}else{
				$output =  '<li id = "'.$row[0].'" ><a onclick="getandParseJson(this);" id = "'.$row[0].'">'.$row[1].'</a></li>';
			     }

		   if($_SESSION['user_id'])echo $output; 
		   }
		   
                ?>
             
            
              
            
             
              
            </ul>
          </div><!--/.well -->
        </div><!--/span-->


        <div class="span9 ">
          <div class="hero-unit main">
	   <h4 id="questionContainer"></h4>
            <p><i id="answerContainer"><i>Please go to the Courses Tab and select courses which you have taken</p>

            
          </div>
          <div >
            <p><a onclick="prevQandA();" style="float:left" class="btn btn-primary btn-large"> &laquo; Previous </a></p>
          <p style="padding-left:8cm;"> <span id="cureentIndex"> 0  </span> / 
            <span id="qandtotal"> 0 </span> </p>
            <p onclick="nextQandA();" style="float:right"><a   class="btn btn-primary btn-large">Next &nbsp &nbsp  &nbsp &nbsp &raquo;</a></p>
          </div>
          
          </div><!--/row-->
        </div><!--/span-->
      </div><!--/row-->

      <hr>

      <footer>
        <p> Capstone Class 2012</p>
      </footer>

    </div><!--/.fluid-container-->




<div id="myModal" class="modal hide fade">
  <div class="modal-header">
    <button type="button"  onclick="showModalEdit();" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
   <textarea id="qContent" style="width:13cm; font-size: 20px;" rows="4" cols="50"  > </textarea>
  </div>
  <div class="modal-body">
    
  <textarea id="aContent" style="width:13cm"  cols="50" rows="6"></textarea>
  </div>
  <div class="modal-footer">
    <a  onclick="showModalEdit();" class="btn">Close</a>
    <a onclick="saveModal();" href="#" class="btn btn-primary">Save changes</a>
  </div>
</div>


 
 

	</div>

	
<?php 



?>

</body>
</html>

  <script src="bootstrap/js/bootstrap.js"></script>
    <script src="bootstrap/js/bootstrap.min.js"></script>
    <link type="text/css" href="css/ui-lightness/jquery-ui-1.8.24.custom.css" rel="stylesheet" />
    
    <script type="text/javascript">

 window.onload = function () {
	    var courseID = $(".firstCourse").attr("id");
	    getandParseJson(courseID);
 }

    </script>
