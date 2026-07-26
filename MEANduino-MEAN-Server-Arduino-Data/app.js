/*
	title: MEANDuino
	author: @paulnurkkala
	description: Simple MEAN-based server to easily create an API to have an Arduino send data back to your server so you can do whatever you want with it in Angular/Node/you name it. 
*/

/* SETTINGS */
//if you have a specific port that you'd like to run this app on, you'll want to change this, otherwise, just leave it alone 
var port_to_run_on  = 5000; 

//settings for Plot.ly 
var plotly_username = ''; 
var plotly_api_key  = '';

//included in settings to encourage you to go look this up 
//grab your database configuration from the db.js file
//in my case, I use mongolab.com to host and create the database because I'm too lazy to set up the servers on my own. In this way, I can really quickly spin up new servers and set passwords, etc. 
//Because this is a small project, I also include my Mongoose definitions in there, though usually you'd want to separate those out into their own files. 
require('./db.js');

/* END SETTINGS */


//Standard express definitions 
var express = require('express'); 
var app = express(); 

//used for parsing POST requests
var bodyParser = require('body-parser');
var multer = require('multer');
app.use(bodyParser.json()); 
app.use(bodyParser.urlencoded({extended:true}));

//set the static and bower components URLs 
app.use('/static', express.static(__dirname+'/public'));
app.use('/bower_components', express.static(__dirname+'/bower_components'));

var bson = require('bson');

//include mongoose to manage the complexity of connecting to a remote database, and serving as the ORM on top of our documents.
var mongoose = require('mongoose'); 
var Temp     = mongoose.model('Temp');


app.get('/', function(req, res){
	res.sendfile('./public/index.html');
});

/*
	description: a GET request, that expects 1 parameter, reading, which is the data that we are attempting to save to our Temp model 
*/
app.get('/send-data', function(req, res){
	//when this function is called, create a new Temp 

	new Temp({
		reading:    req.query.reading, //read the "reading" param from the GET request 
		updated_at: Date.now()         //set the time taken to the current time 
	}).save(function(err, temp, count){
		//now that it's successfully been saved, pass it back for sanity 
		res.json(temp); 
	});
});

/*
	description: go out to the mongodb and grab the data from "Temps" for testing.
*/
app.get('/get-data', function(req, res){
	//find all temp objects
	Temp.find({
		$query: {}, 
		$orderby: {_id: 1}

	//now callback with data 
	},function(err, temps){
  		//if everything went okay, JSON response the data 
  		if(!err){
  			res.json(temps);
  		}
  	});

});

/*
	description: A simple request that builds a URL that's given back by plot.ly, which is to a graph of the data you pass it. You can include that graph in a page or an iFrame or what have you. 
	links: https://plot.ly/
*/
app.get('/plotly-url', function(req, res){
	//query all temps like before 
	Temp.find({
		$query: {}, 
		$orderby: {_id: 1}
	//once we have found all of the temps, send them back and start building out the plot.ly url. 
	}, function(err, temps){
		//if everything worked out 
		if(!err){
   			//initialize some blank slates for gathering data 
   			var x_data = [];
   			var y_data = []; 

			//loop through the data, gathering the x coordinates
			for(var i = 0; i < temps.length; i ++){
				x_data.push(temps[i].updated_at); 
			}

			//loop through the data gathering the y coordinates 
			for(var i = 0; i < temps.length; i ++){
				y_data.push(temps[i].reading); 
			}

			//interface with the plotly Node API
			var plotly = require('plotly')(plotly_username, plotly_api_key);
			var data = [{
				x: x_data,
				y: y_data,
				type: "scatter"
			}];
 			
 			//filename is a simple graph name that plotly will use, and overwrite will update the graph with new data each time it's created. Small-scale, this will work really well. Large scale, I think you'll have to create a new graph name each time you do anything, otherwise people's graphs could be overwritten while they are attempting to view them, which would be sad. 
 			//link to plot.ly tutorial for using node: 
 			//https://plot.ly/nodejs/
			var graphOptions = {filename: "date-axes", fileopt: "overwrite"};
			
			plotly.plot(data, graphOptions, function (err, msg) {
				res.json(msg);
			});

		}
	});
});

app.get('/plotly', function(req, res){
	res.sendfile('./public/plotly.html');
});

//this is an Heroku-specific line
//basically, if process.env.PORT is set by heroku, use that port. If it's not, use the port that is specified above .
app.set('port', (process.env.PORT || port_to_run_on));

//initiate the server
var server = app.listen(app.get('port'), function(){
	var host = server.address().address; 

});

