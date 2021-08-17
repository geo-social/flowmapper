<?php
   $to = $_POST['to']; 
   //Getting the 'to' textbox data from the form

   /* If you are using GET method ,then use $_GET[] */

   $subject = $_POST['name'];
   $comment = $_POST['comment'];
   $email = $_POST['email'];

   // If you leave the $headers from field empty,then your server mail ID will be displayed 
   and it may be moved to the spam section of the email

   mail($to,$subject,$comment,$email);

   /* Done , Your mail will be sent to the email address you want
?>