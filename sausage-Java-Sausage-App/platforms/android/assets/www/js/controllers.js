var sausageControllers = angular.module('sausageControllers', []);

sausageControllers.controller('SausageCtl', ['$scope', '$http',  'SausageFactory', function($scope, $http, SausageFactory){
	$scope.sausage_count = 0; 

	//get count 
	SausageFactory.count().then(function(response){
		console.log(response);
		$scope.sausage_count = response.count; 
	});

	//say sausage 
	$scope.say_sausage = function(){

		var my_media = new Media('/android_asset/www/sounds/sausage.mp3',
            // success callback
            function () {
            	console.log("playAudio():Audio Success");
            },
            // error callback
            function (err) {
            	console.log("playAudio():Audio Error: " + err);
            }
        ); 

		my_media.play();

		SausageFactory.say().then(function(response){
			console.log(response);
			$scope.sausage_count = $scope.sausage_count + 1; 
		});
	}
}]); 