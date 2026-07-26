const EventEmitter = require('events');
const net = require('net');

class StunClient extends EventEmitter {
  constructor(port, address) {
    super();
    this.connected = false;
    this.port = port;
    this.address = address;
    this._connect();
  }

  _connect() {
    this.socket = new net.Socket();
    this.socket.connect(this.port, this.address, () => {
      this.connected = true;
      console.log('STUN client connection established.');
    });

    this.socket.on('data', (rawData) => {
      const data = JSON.parse(rawData);
      if (data.type === 'info') {
        this.emit('info', data);
      } else if (data.type === 'ping') {
        this.emit('ping');
      }
    });

    this.socket.on('close', () => {
      console.log('STUN client connection closed');
      this.connected = false;
      setTimeout(this._connect.bind(this), 1000);
    });

    this.socket.on('error', (err) => {
      console.log('STUN client connection error occurred.');
    });
  }
}

module.exports = StunClient;