### Zylo Weather Getter
Author: Paul Nurkkala // paulnurkkala@gmail.com 

This is a quick application put together on behalf of Zylo as part of the interview process. 

## Requirements: 
* You will build an application that takes data, stores it and displays it. By data, we mean a collection of data points that have at least a date and a numeric value. Examples of some good API sources: https://en.wikipedia.org/wiki/List_of_open_APIs
* We require you to use the same stack we use at Zylo. It means a Node.js & Express backend and JavaScript (React optional) client. Beside that, you are free to use whatever technology you want.

## How This meets Requirements 
* Takes Data
  * The way that I handled "taking" data was maybe a bit sneaky, but I essentially made the input based on the browser's GPS coordinates, rather than having the user type something in. 
* Stores it
  * The application stores data in a Mongo DB database using the Mongoose wrapper to control the schemas. The username and password to that mongo instance is provided in the webapp 
* Displays it
  * The data display is a very simple table that shows the tempeture at the given date that the user clicked the button to record the information. While the only information that's shown is temp, much more data is recorded.

## Notes
* I elected not to use a library for the forecast.io API for the purpose of the exercise, despite that it's a fairly simple API in the first place 
* I didn't organize the project quite as well as I could have, but that's simply for the purpose of time. I didn't need to spend the time creating a really heavy weight file organization for something like this. (I.e. all of my angular services and controllers are in one file). 
* I uploaded all of the libraries and files and whatnot directly to the repository for the sake of simplicity. You SHOULD be able to just download the whole thing and run it right off the spot.
* The node_modules are included in the public static hosting part of express via a natural link to the node_modules folder in the root directory 

## Files of Interest
* These files are the ones that are worth looking at for the entire project: 
* NodeJS App: [https://github.com/paulnurkkala/zyloweathergetter/blob/master/app.js](https://github.com/paulnurkkala/zyloweathergetter/blob/master/app.js)
* Home Template: [https://github.com/paulnurkkala/zyloweathergetter/blob/master/templates/index.html](https://github.com/paulnurkkala/zyloweathergetter/blob/master/templates/index.html)
* Angular App: [https://github.com/paulnurkkala/zyloweathergetter/blob/master/public/angularapp.js](https://github.com/paulnurkkala/zyloweathergetter/blob/master/public/angularapp.js)
* Angular View Template [https://github.com/paulnurkkala/zyloweathergetter/blob/master/public/angular-parts/home.html](https://github.com/paulnurkkala/zyloweathergetter/blob/master/public/angular-parts/home.html)
* Mongoose Models: [https://github.com/paulnurkkala/zyloweathergetter/tree/master/model](https://github.com/paulnurkkala/zyloweathergetter/tree/master/model)
