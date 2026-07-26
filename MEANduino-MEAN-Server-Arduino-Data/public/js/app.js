'use strict'; 

var chartApp = angular.module('chartApp',[
    'chartControllers', 
    'chartFactories',
    'ngSanitize', 
    'ngRoute'
]);

/*
	description: set up the routing for the angular application 
*/
chartApp.config(['$routeProvider',function($routeProvider){
	$routeProvider.
	    when('/', {
	    	templateUrl: '/static/partials/home.html',
	    	controller: 'HomeController'
	    }).

	    when('/demo', {
	    	templateUrl: '/static/partials/demo.html',
	    	controller:  "DemoController"
	    }).

	    otherwise({
	    	redirectTo: '/'
	    }); 

}]);

