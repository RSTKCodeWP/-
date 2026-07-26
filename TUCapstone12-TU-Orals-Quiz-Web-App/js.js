$(document).ready(function() {
    $.post('view_courses.php', function(data) {
	$('.course_list').html(data);
    });
    $.post('view_users.php', function(data) {
	$('.user_list').html(data);
	$('.user_list').bind('change', function(){
	    var user = document.getElementById("user_list");
	    var selectedText = user.options[user.selectedIndex].text;
	    var userID = ($('#user_list').val());
	   $.post('set_user_session.php', {userid: userID, username: selectedText}, function(data){
		$.post('show_user.php', function(data){
		    if(data){
			$('.user_list').html('You are now logged in as ' + data + '.'); 
		    }
		});
	    });
	});
    });
    
    $('.new_user_button').bind('mouseup', function(){
	var id = ($('.new_user').val());
	var user = ($('.new_user').val()); 
	$.post('set_user_session.php', {id: id, user: user}, function(data){
	    $.post('show_user.php', function(data){
    		$.post('add_user.php', {id: id, user: user}, function(data){
		    console.log(data);
		});
		if(data){
		    $('.user_list').html('You are now logged in as ' + data + '.'); 
		}
	    });
	});
    });




    $('.random_button').bind('mouseup', function(){
	$.post('random_question.php', function(data){
	    $('.question_content').html(data);

   $('.show_answer').bind('mouseup', function(){
	console.log('show answer button pressed');
	$qid = $('.show_answer').data('qid'); 
	$.post('question_answer.php', {qid: $qid},  function(data){
	    $('.question_answer').html(data);
	});
    });

	});
    });

 
});

function saveUserCourse(course){
	var courseID = $(course).val();
	var checked = course.checked;
	var userId = $(course).attr("user");
	$.post('save_course.php',{course:courseID, userID: userId, selected:checked}, function(data){
		if(data){
			alert(data);
		}
	    });

	}
