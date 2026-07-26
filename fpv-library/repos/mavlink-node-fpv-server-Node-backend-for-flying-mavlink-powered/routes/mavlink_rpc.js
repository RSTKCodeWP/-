const Eureca = require('eureca.io');

class MavlinkRPC {
  constructor(app, mav) {
    //this.server = new Eureca.Server({allow : ['mavlinkrpc.message'], transport: 'sockjs'});
    this.server = new Eureca.Server({allow : ['onMessage']});
    this.connections = {};
    this.app = app;
    this.mav = mav;
    this.server.onConnect(this._onConnect.bind(this));
    this.server.onDisconnect(this._onDisconnect.bind(this));
    this.info = {
      serialPath: {
        port: undefined,
        address: undefined
      }, 
      videoPath: {
        port: undefined,
        address: undefined
      }
    };

    this.server.exports = {
      hello: () => {
        console.log('Got hello from client');
      }
    };

    mav.on('data', this._onHardwareLinkMessage.bind(this));

    this.server.attach(this.app.server);
    //console.log(this.server.onConnect);
 
    // tchatServer.login = function (nick) {
    //  console.log('Client %s auth with %s', this.connection.id, nick);
    //  var id = this.connection.id;
    //  if (nick !== undefined) //here we can check for login/password validity for example
    //  {
    //   connections[id].nick = nick;  
      
    //   //tchat.welcome() is a client side function indicated that the client authentication is ok
    //   connections[id].client.tchat.welcome();
    //  }
    // }
  }

  _onConnect(connection) {
    console.log('New client ', connection.id, connection.eureca.remoteAddress);
    this.connections[connection.id] = { client: connection.clientProxy };
    this._sendToAll('info', this.info);
  }

  _onDisconnect(connection) {
    console.log('Client quit', connection.id);
    delete this.connections[connection.id];
  }

  _sendToAll(event, fields) {
    for (var key in this.connections) {
      if (this.connections.hasOwnProperty(key)) {
        const connection = this.connections[key];
        connection.client.onMessage(event, fields);
      }
    }
  }

  _onHardwareLinkMessage(event, fields) {
    if (event === 'info.serialPath') {
      this.info.serialPath = {
        port: fields.port,
        address: fields.address
      };
    } else if (event === 'info.videoPath') {
      this.info.videoPath = {
        port: fields.port,
        address: fields.address
      };
    } else {
      this._sendToAll(event, fields);
    }
  }
}


module.exports = MavlinkRPC;
