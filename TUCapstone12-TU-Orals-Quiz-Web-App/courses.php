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
		<script type="text/javascript" src="dropdown.js"> </script>
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
			      <li><a href="index.php">Home (<?php echo $_SESSION['user'] ?>) </a></li>
			      <li><a href="questions.php">Questions</a></li>
			      <li class="active"><a href="courses.php">Courses</a></li>
			      <li><a href="logout.php">Logout</a></li>
			    </ul>
			</div>
		     </div>
	     <!-- End Navbar --> 

		<div class="course_list">
		</div>
	</div>

	
<?php 
?>

</body>
</html>
