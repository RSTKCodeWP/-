from pymavlink import mavutil


class WaypointManager:

    def __init__(self):

        self.waypoints = []

    def add_waypoint(
        self,
        latitude,
        longitude,
        altitude
    ):

        waypoint = {

            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude
        }

        self.waypoints.append(waypoint)

        print("Waypoint Added")

    def show_waypoints(self):

        for i, wp in enumerate(self.waypoints):

            print(
                f"{i+1}: "
                f"{wp}"
            )


if __name__ == "__main__":

    manager = WaypointManager()

    manager.add_waypoint(
        28.6139,
        77.2090,
        120
    )

    manager.show_waypoints()
