import uvicorn
from flight_safety.config import Settings
from flight_safety.bridge import FlightBridge
from flight_safety.dispatcher import Dispatcher
from flight_safety.server import build_app


def main() -> None:
    settings = Settings()
    bridge = FlightBridge(settings.mavlink_address)
    dispatcher = Dispatcher(bridge, settings.limits, settings.geofence)
    # Connect the bridge inside the server's own event loop (MAVSDK gRPC objects
    # bind to the loop that creates them); connecting in a separate asyncio.run()
    # would bind them to a loop that is then closed before requests are served.
    app = build_app(dispatcher, on_startup=lambda: bridge.connect(timeout_s=30))
    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
