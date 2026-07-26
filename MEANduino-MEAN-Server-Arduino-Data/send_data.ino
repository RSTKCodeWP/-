#include <SPI.h>
#include <Ethernet.h>
 
// Enter a MAC address for your controller below.
// Newer Ethernet shields have a MAC address printed on a sticker on the shield
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };

// if you don't want to use DNS (and reduce your sketch size)
// use the numeric IP instead of the name for the server:
char server[] = "node.paulnurkkala.com";    // name address for your webserver 
 
// Set the static IP address to use if the DHCP fails to assign
// As far as I can tell, this can be whatever you want, as long as it's an IP address
IPAddress ip(192,168,0,177);
 
// Initialize the Ethernet client library
// with the IP address and port of the server
// that you want to connect to (port 80 is default for HTTP):
EthernetClient client;

//pick the PIN that the temperature sensor is running on 
const int temperaturePin = 0;
 
void setup() {

  // Open serial communications and wait for port to open:
  Serial.begin(9600);
   while (!Serial) {
    ; // wait for serial port to connect. Needed for Leonardo only
  }
}
 
void loop()
{
  //from here, all we have to do is call the function to send data to the server 
  send_data(get_temperature());

  //print this to the serial so that you can see it in case something fails when you attempt to send to server 
  Serial.println(get_temperature());

  //wait 1 minute 
  delay(60000);
}
 
void send_data(float data){
  // start the Ethernet connection:
  if (Ethernet.begin(mac) == 0) {
    Serial.println("Failed to configure Ethernet using DHCP");
    // no point in carrying on, so do nothing forevermore:
    // try to congifure using IP address instead of DHCP:
    Ethernet.begin(mac, ip);
  }

  // give the Ethernet shield a second to initialize:
  delay(1000);
  Serial.println("connecting...");

  //at this point, we're connected to the network, but we haven't sent any data off to the server.

  // if you get a connection, report back via serial:
  if (client.connect(server, 80)) {
    Serial.println("connected");

    // Make a HTTP request:

    //this chunk builds the GET request 
    client.print("GET /send-data?reading=");
    client.print(data);
    client.println(" HTTP/1.1");

    //this sets the host that's going to be requested by the GET request
    client.println("Host: node.paulnurkkala.com");

    //and then quit the connection
    client.println("Connection: close");
  }
 
  // if the server's disconnected, stop the client:
  //basically, now that we're done with the request, we need to tell arduino to kill the connection and get ready to refresh 
  if (!client.connected()) {
    Serial.println();
    Serial.println("disconnecting.");
    client.stop();
  }
}

//gets a temp in F from the device 
float get_temperature(){
  //analog read the temperature pin, gathering an amount of voltage 
  int reading = analogRead(temperaturePin);
 
  //not sure why this is a part of the step, but it is 
  //taken from here: https://learn.adafruit.com/tmp36-temperature-sensor/using-a-temp-sensor
  float voltage = reading * 5.0;
  voltage /= 1024.0;

  //convert to celcius 
  float tempC = (voltage - .5) * 100;

  //convert to F
  float tempF = (tempC * 9.0 / 5.0 ) + 32.0;

  //print it 
  Serial.print(tempF); Serial.println(" degreesF");

  //return it 
  return tempF;
 
}