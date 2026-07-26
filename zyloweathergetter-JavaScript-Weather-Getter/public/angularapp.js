//define the angular app, pulling in libraries that will be needed 
var app = angular.module('webApp', [
	'webAppControllers', 
	'webAppServices',
	'ngRoute',
	'ui.bootstrap'
]);

//define angular routes -- only one is used for this app, but I put it in so that future expansion would be available 
app.config(['$routeProvider', function($routeProvider) {
	console.log('routing');
   $routeProvider.
   
   when('/', {
      templateUrl: '/angular-parts/home.html', controller: 'HomeController as hc'
   }).
   
   otherwise({
      redirectTo: '/'
   });
	
}]);

/*
	borrowed from: http://stackoverflow.com/questions/23185619/how-can-i-use-html5-geolocation-in-angularjs
	description: Quick service for pulling the Lat/Lon out of the browser and bringing the coordinates into scope 
*/
var services = angular.module('webAppServices', []);
services.service('webApp', []).factory('geolocationSvc', ['$q', '$window', function ($q, $window) {

    function getCurrentPosition() {
    	console.log('entering');
        var deferred = $q.defer();

        if (!$window.navigator.geolocation) {
            deferred.reject('Geolocation not supported.');
        } else {
            $window.navigator.geolocation.getCurrentPosition(
                function (position) {
                    deferred.resolve(position);
                },
                function (err) {
                    deferred.reject(err);
                });
        }

        return deferred.promise;
    }

    return {
        getCurrentPosition: getCurrentPosition
    };
}]);

/*
	author: @paulnurkkala
	description: service for interacting with our webapp's weather API 
*/
services.factory('weather', ['$http',  function($http){
	return{
		//called when the user wants to retrieve new information 
		get_weather: function(lat, lon){
			var response = $http({
				url: '/weather/', 
				method: "POST",
				data: {
					'lat': lat, 
					'lon': lon
				},					
			}).then(function(response){
				return response.data;
			}); 
			return response;			
		}, 

		//called when the user loads the page, and imports all gathered weather data into the view
		old_data: function(){
			var response = $http({
				url: '/old-data',
				method: "GET", 
			}).then(function(response){
				return response.data;
			});
			return response; 
		}
	};
}])


//controllers 
var ctrls = angular.module('webAppControllers', []);

/*
	author: @paulnurkkala
	description: Controller for the home page. All view logic is contained within.
*/
ctrls.controller('HomeController', ['$scope', '$http', 'geolocationSvc', 'weather', function($scope, $http, geolocationSvc, weather){
	var self = this; 
	self.coordinates = {};
	self.weather_rows = [];
	self.old_data = {}; 

	//fetch lat/lon from the browser and save to be used later
	geolocationSvc.getCurrentPosition().then(function(location){
		self.coordinates = location.coords;
	});

	//just a wrapper function to clean up checking to see whether or not coords are loaded
	self.coordsLoaded = function(){
		return ( self.coordinates.latitude && self.coordinates.longitude ); 

	}

	//when the user clicks the button on the page, this is called, asking the webapp API to grab, save, and return weather information based on the "input" which is the local lat/lon of the user
	self.get_weather = function(){
		weather.get_weather(self.coordinates.latitude, self.coordinates.longitude).then(function(response){
			response.created = new Date();
			self.weather_rows.push(response);
		});
	}

	//when the page is loaded, we ask the webapp for any existing and already saved weather information, which is slightly modified for display structure, and then displayed to the user
	self.get_old_data = function(){
		weather.old_data().then(function(response){
			self.old_data = response;
			for (var i = 0; i < response.length; i++) {
				to_return = response[i].data; 
				to_return.created = response[i].created;
				self.weather_rows.push(to_return);
			};
		});
	}

	//call this on page load
	self.get_old_data();
}]);
