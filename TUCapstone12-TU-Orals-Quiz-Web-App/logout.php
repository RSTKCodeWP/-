<?php 
      session_start(); 
      $_SESSION['user'] = null;
      $_SESSION['user_id'] = null;
      
      echo 'you are now logged out.';

      header('Location: index.php');