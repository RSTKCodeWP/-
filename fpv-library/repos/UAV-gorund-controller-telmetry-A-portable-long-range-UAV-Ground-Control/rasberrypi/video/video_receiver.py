import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 5600

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

sock.bind((UDP_IP, UDP_PORT))

print("Video Receiver Started")

while True:

    data, addr = sock.recvfrom(65535)

    print(
        f"Received video packet "
        f"from {addr}"
    )


import cv2
import time

cap = cv2.VideoCapture(0)

fourcc = cv2.VideoWriter_fourcc(*'XVID')

filename = f"flight_{int(time.time())}.avi"

out = cv2.VideoWriter(
    filename,
    fourcc,
    20.0,
    (640, 480)
)

print("Recording Started")

while True:

    ret, frame = cap.read()

    if not ret:
        break

    out.write(frame)

    cv2.imshow(
        'Recording',
        frame
    )

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out.release()

cv2.destroyAllWindows()

