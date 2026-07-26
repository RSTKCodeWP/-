const EventEmitter = require('events');
const net = require('net');

class StunServer extends EventEmitter {
  constructor(ports) {
    super();
    this.socket = null;
    this.connections = {};
    this.servers = {};

    for (var i = ports.length - 1; i >= 0; i--) {
      const port = ports[i];
      const server = this.servers[port] = net.createServer((socket) => {
        console.log(`New stun connection on port ${port}`);
        this.connections[socket] = {
          timer: setInterval(this._ping(socket), 1000)
        };
        socket.setKeepAlive(true);
        socket.on('close', this._disconnect(socket));
        socket.on('error', () => {}); // do nothing
        this._sendInfo(socket);
      });
      server.listen(port, '0.0.0.0');
      console.log('STUN on port ' + port);
    };
  }

  _ping(socket) {
    return () => {
      socket.write(JSON.stringify({ 
        type: 'ping'
      }));
    };
  }

  _disconnect(socket) {
    return () => {
      try {
        clearInterval(this.connections[socket].timer);
        delete this.connections[socket];
      } catch (ex) {

      }
    };
  }

  _sendInfo(socket) {
    socket.write(JSON.stringify({
      type: 'info',
      address: socket.remoteAddress,
      port: socket.remotePort
    }));
  }
}


module.exports = StunServer;