'use strict';

var sausageServices = angular.module('sausageServices', []);

var remote_url = 'http://meanduino.paulnurkkala.com/';
sausageServices.factory('SausageFactory', ['$http', 
	function($http){
		return{
			count: function(restaurant){
				var response = $http({
				    url: remote_url + 'sausages/count/',
				    method: "GET",
				}).then(function(response){
					return response.data;
				});
				return response;
			}, 
			say: function(restaurant){
				var response = $http({
				    url: remote_url + 'sausage/',
				    method: "GET",
				}).then(function(response){
					return response.data;
				});
				return response;
			}
		}
	}
]);
