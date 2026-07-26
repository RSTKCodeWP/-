const net = require('net');

class ServerLink {
  constructor(port, address) {
    this.connected = false;
    this.port = port;
    this.address = address;
    this._connect();
  }

  _connect() {
    this.socket = new net.Socket();
    this.socket.connect(this.port, this.address, () => {
      //this.socket.write('Hello, server! Love, Client.');
      this.connected = true;
      console.log('Server connection established.');
    });

    this.socket.on('data', (data) => {
      console.log('Received: ' + data);
    });

    this.socket.on('close', () => {
      console.log('Server connection closed');
      this.connected = false;
      setTimeout(this._connect.bind(this), 1000);
    });

    this.socket.on('error', (err) => {
      console.log('Server connection error occurred.');
    })
  }

  send(data, persistent) {
    if (this.connected) {
      this.socket.write(JSON.stringify(data) + '\n');
    } else if (!this.connected && persistent) {
      setTimeout(() => {
        this.send(data, false);
      }, 1000);
    }
  }
}

module.exports = ServerLink;