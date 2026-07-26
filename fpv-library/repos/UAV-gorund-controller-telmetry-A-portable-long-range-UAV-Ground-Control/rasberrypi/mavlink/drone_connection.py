from pymavlink import mavutil


class DroneConnection:

    def __init__(
        self,
        port='/dev/ttyUSB0',
        baud=57600
    ):

        self.master = mavutil.mavlink_connection(
            port,
            baud=baud
        )

        self.master.wait_heartbeat()

        print("Drone Connected")

    def arm(self):

        self.master.arducopter_arm()

        print("Drone Armed")

    def disarm(self):

        self.master.arducopter_disarm()

        print("Drone Disarmed")

    def set_mode(self, mode):

        mode_id = self.master.mode_mapping()[mode]

        self.master.set_mode(mode_id)

        print(f"Mode Set: {mode}")


if __name__ == "__main__":

    drone = DroneConnection()

    drone.arm()

    drone.set_mode("GUIDED")

