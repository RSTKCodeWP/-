/* SETTINGS */
//put your database connection here 
var db_username    = '';
var db_password    = ''; 
var db_address     = '';
/* END SETTINGS */ 

var mongoose = require('mongoose');
var Schema   = mongoose.Schema;

var Temp = new Schema({
	id         : String, 
	reading    : String,
	updated_at : Date
});

mongoose.model('Temp', Temp); 


//Uncomment this line and replace the rest of the URLS with the real 
var db_host_string = 'mongodb://' + db_username + ':' + db_password + '@' + db_address; 

//perform actual connection to the database 
mongoose.connect(db_host_string);