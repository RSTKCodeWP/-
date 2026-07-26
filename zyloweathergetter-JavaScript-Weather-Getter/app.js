//load a bunch of libraries and database elements
var express = require('express'); 
var http = require('http');
var https = require('https');
var request = require('request');
var bodyParser = require('body-parser');
var multer = require('multer');
var app = express();
var db = require('./model/db')
var tempData = require('./model/Temp').Temp;
var mongoose = require('mongoose');  

//load static files
app.use(express.static('public'));

//required for static files
app.use(bodyParser.json());
app.use(multer({dest:'./uploads/'}).single('photo'));

//API key used to pull data from the forecast API 
var forecast_key = '41135a8cec32877f4d720b73b3750620';

//tell express where the templates are 
var template_options = {
	root: __dirname + '/templates/',
	dotfiles: 'deny',
};


/*
	author; @paulnurkkala
	description: Simple view to display an HTML template, from which the angular app is driven 
*/
app.get("/", function(req, res){
	res.sendFile('index.html', template_options, function(){});
});

/*
	author: @paulnurkkala
	description: API endpoint for pulling data out of Mongo and back into the webapp. Very simple -- just pulls all data points. 
*/
app.get('/old-data', function(req, res){
	tempData.find().exec(function(err, datas){
		var to_return = [];

		//I needed to convert a JSON string into a JSON object, and a shallow modification wasn't working, so I made a deep copy to push out the data back to the front end 
		for (var i = 0; i < datas.length; i++) {
			//deep copy 
			to_return.push({
				'lat': datas[i].givenLat,
				'lon': datas[i].givenLon, 
				'created': datas[i].created,
				'data': JSON.parse(datas[i].data) 
			});
		};
		res.send(to_return);
	});
});

/*
	author: @paulnurkkala
	description: API endpoint for getting weather information. In order to maintain the security of the private key for accessing the API, we need to call the API from our server. This function simply calls the API on our behalf, and returns the data. In addition, it also saves the data to our mongoDB instance so as to reuse that information later without having to reaccess the weather Database. It's am much less expensive operation to pull it from the Mongo Document than to wait for it to come across from the weather API. 
*/
app.post('/weather', function(req, res){
	//pull POST variables out
	var lat, lon; 
	lat = req.body.lat; 
	lon = req.body.lon;

	//generate the forecast API URL. I intentionally didn't use any NODE libraries for the Darkskies forecast API for the purpose of the exercise. 
	var url = 'https://api.forecast.io/forecast/'+forecast_key+'/'+lat+','+lon;
	request(url, function(error, response, body) {
		json = JSON.parse(body);

		//save information to the database 
		tempData.create({
			givenLat: lat, 
			givenLon: lon, 
			created: new Date(),
			data: body
		}, function (err, small) {
			if (err) return handleError(err);
		})

		//send the gathered data back to the frontend to be displayed to the user
		res.send(json);
	});
});

app.listen(3000, function () {
	console.log('Example app listening on port 3000!');
});
