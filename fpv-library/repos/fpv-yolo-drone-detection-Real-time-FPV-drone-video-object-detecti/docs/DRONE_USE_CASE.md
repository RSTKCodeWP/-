# Drone / FPV Use-Case Explanation

## Project Summary

This project demonstrates a real-time object detection pipeline for FPV and drone video. A YOLO model processes each incoming frame, OpenCV handles the video source and output stream, and the system records detections and FPS metrics.

## Why This Matters for UAV / Aerospace Roles

A drone perception stack typically needs to answer practical questions in real time:

- Is there a person, vehicle, obstacle, structure, landing marker, or moving object in the frame?
- How fast can the onboard computer process the video feed?
- Is the perception system stable enough for field use?
- Can the model run at the edge on Jetson-class hardware?
- Can the detection output be logged for post-flight analysis?

## Possible Applications

### Search and Rescue Support

Detect people, vehicles, or visible objects in wide-area video. This must be treated as decision support, not a replacement for trained responders.

### Infrastructure Inspection

Detect objects of interest around bridges, towers, roofs, solar farms, ports, or industrial sites. With a custom dataset, the model can be fine-tuned for cracks, corrosion, panels, insulators, or asset-specific targets.

### Field Robotics and Autonomy

Use detections as perception inputs for navigation, obstacle awareness, target following, or scene understanding.

### Defense and Security Research

Use only within lawful, ethical, and authorized contexts. Keep the project framed around perception, inspection, safety, and robotics research.

## Limitations

Default COCO-trained YOLO models are not specialized for aerial footage. Common weaknesses include small objects at altitude, motion blur, low-light scenes, aggressive FPV camera angles, and domain shift.

## Next Improvements

- Fine-tune on drone/aerial datasets.
- Add object tracking such as ByteTrack or BoT-SORT.
- Add geotagged detections using GPS logs.
- Add MAVLink telemetry overlay.
- Add ROS 2 node integration.
- Add TensorRT benchmarking on Jetson.
- Add RTSP/UDP receiver pipeline for actual FPV feed.
