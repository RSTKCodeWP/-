var mongoose = require('mongoose');  

//define weather information schema.
var tempSchema = new mongoose.Schema({
	givenLat: Number,
	givenLon: Number,
	created: Date, 
	data: String
});
var Temp = mongoose.model('Temp', tempSchema);

//make the object available as an importable library
module.exports = {
  Temp: Temp
}