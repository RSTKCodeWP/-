import cv2 as cv
from datetime import datetime

# mobilenet config
config_file = 'mobilenet/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'   # mobilenet configuration
frozen_model = 'mobilenet/frozen_inference_graph.pb'  # mobilenet weights
label_names = 'mobilenet/label_names_flat'  # name of labels
# video output
output_filename = 'output/fpv_opencv_mobssd_' + datetime.now().strftime("%d%m%Y_%H%M%S") + '.mp4'
output_frames_per_second = 20.0
file_size = (1920,1080)

# define the model
model = cv.dnn_DetectionModel(frozen_model, config_file)
model.setInputSize(320, 320)
model.setInputScale(1.0/127.5)
model.setInputMean((127.5, 127.5, 127.5))
model.setInputSwapRB(1)

# label names
classLabels = []
with open(label_names, 'rt') as fpt:
    classLabels = fpt.read().strip('\n').split('\n')

# font for output in video
font_scale = 3
font = cv.FONT_ITALIC

# capture the stream from saved video
stream = cv.VideoCapture("videos/opencv_test.mov")
# capture the stream from webcam
# stream = cv.VideoCapture(0)
if not stream.isOpened():
    stream = cv.VideoCapture(0)
if not stream.isOpened():
    raise IOError("Can not open video")

# create a VideoWriter object for saving the video output
fourcc = cv.VideoWriter_fourcc(*'mp4v')
result = cv.VideoWriter(output_filename,
                         fourcc,
                         output_frames_per_second,
                         file_size)

while True:
    ret, frame = stream.read()
    ClassIndex, confidence, bbox = model.detect(frame, confThreshold=0.55)

    print(ClassIndex)
    if (len(ClassIndex) != 0):
        for ClassInd, conf, boxes in zip(ClassIndex.flatten(), confidence.flatten(), bbox):
            if (ClassInd <= 80):
                cv.rectangle(frame, boxes, (255, 0, 0),2)
                cv.putText(frame, classLabels[ClassInd-1], (boxes[0]+10, boxes[1]+40), font, fontScale=font_scale, color=(0,255,0), thickness=3)

    cv.imshow('First opencv flight video', frame)
    result.write(frame)

    if cv.waitKey(2) & 0xFF == ord('q'):
        break

stream.release()
result.release()
cv.destroyAllWindows()
