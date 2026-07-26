import cv2

stream_url = 0

cap = cv2.VideoCapture(stream_url)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    cv2.imshow(
        "FPV Stream",
        frame
    )

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()

cv2.destroyAllWindows()
```

