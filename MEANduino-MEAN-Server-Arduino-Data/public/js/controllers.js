'use strict';

var chartControllers = angular.module('chartControllers',[]);

chartControllers.controller("ChartController", ["$scope", "$http", function($scope, $http){
	
}]);

chartControllers.controller("HomeController", ["$scope", '$http', function($scope, $http){
	console.log("welcome");
}]);

chartControllers.controller("DemoController", ["$scope", "$http", "$sce", function($scope, $http, $sce){
	$scope.loading=true;
	$scope.trustSrc = function(src) {
		return $sce.trustAsResourceUrl(src);
	};

	var response = $http({
		url: '/plotly-url', 
		    method: "GET", 
		    params: {}, 
		}).then(function(response){
			$scope.plotly_url = response.data.url;
			$scope.loading = false; 
	});
}]);
