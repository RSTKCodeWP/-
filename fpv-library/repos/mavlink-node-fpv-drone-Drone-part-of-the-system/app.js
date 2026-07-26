const mavlink = require('mavlink');
const mav = new mavlink(1,1,"v1.0",["common", "ardupilotmega"]);

const SerialPort = require('serialport');
const ServerLink = require('./modules/server_link');
const StunClient = require('./modules/stun_client');

const serverAddress = '127.0.0.1';

const serverLink = new ServerLink(7800, serverAddress);

let port = null;

function sendStunInfo(type) {
  return (info) => {
    serverLink.send({
      type: type,
      port: info.port,
      address: info.address
    });
  }
}

new StunClient(7801, serverAddress).on('info', sendStunInfo('info.videoPath'));
new StunClient(7802, serverAddress).on('info', sendStunInfo('info.serialPath'));

function connectSerial() {
  port = new SerialPort('/dev/ttyACM0', {
    baudRate: 115200
  });

  port.on('error', function(err) {
    console.log('Error: ', err.message);
    setTimeout(connectSerial, 5000);
  });

  port.on('open', function() {
    console.log('Flight controller connection established.');
  });
}

connectSerial();

mav.on("ready", function() {
  port.on('data', function(data) {
    mav.parse(data);
  });

  mav.on('ATTITUDE', function(message, fields) {
    serverLink.send({
      type: 'ATTITUDE',
      fields: fields
    });
  });
  
  mav.on('VFR_HUD', function(message, fields) {
    serverLink.send({
      type: 'VFR_HUD',
      fields: fields
    });
  });
});
