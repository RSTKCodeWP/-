/**
 * SimWorld - the multi-vehicle container. Runs one JSON-FDM UDP server per
 * vehicle (each SITL instance connects to its own port) and streams all vehicle
 * states out through a single shared state WebSocket. Wind config is shared so
 * every vehicle flies in the same conditions.
 */

import { FdmServer } from './fdm-server.js';
import { StateWebSocketServer } from './state-ws.js';
import { SimVehicle } from './vehicle.js';

export interface WorldVehicle {
  vehicle: SimVehicle;
  fdmPort: number;
}

export class SimWorld {
  private servers: FdmServer[] = [];
  private readonly ws: StateWebSocketServer;

  constructor(
    private readonly vehicles: WorldVehicle[],
    wsPort: number,
  ) {
    this.ws = new StateWebSocketServer(wsPort);
  }

  async start(): Promise<void> {
    this.ws.start();
    for (const wv of this.vehicles) {
      const server = new FdmServer(wv.fdmPort, wv.vehicle, (id, state) => {
        this.ws.update(id, state, wv.vehicle.home, wv.vehicle.batteryVoltage);
      });
      await server.start();
      this.servers.push(server);
    }
  }

  stop(): void {
    for (const s of this.servers) s.stop();
    this.servers = [];
    this.ws.stop();
  }
}
