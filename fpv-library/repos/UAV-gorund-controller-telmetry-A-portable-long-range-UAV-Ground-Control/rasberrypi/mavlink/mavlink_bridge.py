from pymavlink import mavutil

master = mavutil.mavlink_connection(
    '/dev/ttyUSB0',
    baud=57600
)

master.wait_heartbeat()

print("Heartbeat Received")


while True:

    msg = master.recv_match(
        blocking=True
    )

    if msg:

        print(msg)


