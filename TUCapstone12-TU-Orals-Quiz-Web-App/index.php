<?php
   session_start();
   include 'db_connect.php';
?>
<html>
	<head>
		<title>TU Capstone Study 2012</title>
		<script type="text/javascript" src="jquery.js"> </script>
		<script type="text/javascript" src="js.js"> </script>
		<script type="text/javascript" src="bootstrap/js/bootstrap.js"> </script>
		<link rel="stylesheet" type="text/css" href="css.css" />
		<link rel="stylesheet" type="text/css" href="bootstrap/css/bootstrap.min.css" />


	</head>

	<body>
		<div class="container">
		     <!-- Navbar --> 
		     <div class="navbar">
			<div class="navbar-inner">
			    <a class="brand" href="index.php">TU Capstone Study 2012</a>
			    <ul class="nav">
			      <li class="active"><a href="index.php">Home (<?php echo $_SESSION['user'] ?>) </a></li>
			      <li><a href="questions.php">Questions</a></li>
			      <li><a href="courses.php">Courses</a></li>
			      <li><a href="quiz.php">Quiz</a></li>
			      <li><a href="logout.php">Logout</a></li>
			    </ul>
			</div>
		     </div>

		     <!-- End Navbar --> 
		<p>Welcome to the TU computer science capstone studying website.</p>
		<p><b>Who are you?</b> (Whatever you say here
		will be chached and reported to everyone else)</p>
		<div class="user_list" value="">
		</div>

		<div class="add_user">
		     <p> Or.. add user </p>
		     <input class="new_user"/><button class="new_user_button">Add</button>
		</div>
		<br/>
		
</div>
	</body>
</html>
