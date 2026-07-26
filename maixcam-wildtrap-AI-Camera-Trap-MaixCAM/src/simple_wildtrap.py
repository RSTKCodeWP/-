
#!/usr/bin/env python3
"""
Simple WildTrap - Educational Version
Minimal camera trap implementation for learning

This simplified version demonstrates core concepts:
- Camera capture
- Motion detection
- AI object detection
- File saving

Perfect for understanding the basics before diving into the full app.
"""

import os
import time
from datetime import datetime
from pathlib import Path

try:
    from maix import camera, display, image, nn
except ImportError:
    print("MaixPy not available - simulation mode")
    camera = display = image = nn = None


# Configuration
SAVE_DIR = Path("/root/wildtrap_simple")
SAVE_DIR.mkdir(exist_ok=True)

TARGET_OBJECTS = ["person", "dog", "cat", "bird"]
CONFIDENCE_THRESHOLD = 0.6
COOLDOWN_SECONDS = 10

# COCO class names (subset)
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"
]


class SimpleWildTrap:
    """Minimal camera trap implementation."""
    
    def __init__(self):
        self.cam = None
        self.disp = None
        self.model = None
        self.previous_frame = None
        self.last_capture_time = 0
        
    def initialize(self):
        """Setup camera and AI model."""
        print("Initializing Simple WildTrap...")
        
        # Initialize camera
        if camera:
            self.cam = camera.Camera(640, 480)
            self.disp = display.Display()
            print("✓ Camera ready")
        else:
            print("✗ Camera not available")
            return False
        
        # Load AI model
        if nn:
            model_path = "/root/models/yolov8n.mud"
            if os.path.exists(model_path):
                self.model = nn.YOLOv8(model=model_path)
                print("✓ AI model loaded")
            else:
                print("✗ AI model not found")
        
        print("Initialization complete!\n")
        return True
    
    def detect_motion(self, img):
        """Simple motion detection using frame differencing."""
        if img is None:
            return False
        
        # Convert to grayscale and resize for speed
        gray = img.to_grayscale()
        small = gray.resize(160, 120)
        
        # First frame - no motion yet
        if self.previous_frame is None:
            self.previous_frame = small
            return False
        
        # Calculate difference from previous frame
        diff = small.difference(self.previous_frame)
        self.previous_frame = small
        
        # Motion detected if significant difference
        # (In real implementation, would count changed pixels)
        return True  # Simplified
    
    def detect_objects(self, img):
        """Detect objects using YOLOv8."""
        if not self.model or img is None:
            return []
        
        # Run AI inference
        results = self.model.detect(img)
        
        # Filter for target objects
        detected = []
        for obj in results:
            class_id = obj.class_id
            confidence = obj.score
            
            # Get object label
            if class_id < len(COCO_CLASSES):
                label = COCO_CLASSES[class_id]
            else:
                continue
            
            # Check if it's a target object with sufficient confidence
            if label in TARGET_OBJECTS and confidence >= CONFIDENCE_THRESHOLD:
                detected.append({
                    "label": label,
                    "confidence": confidence,
                    "bbox": obj.box
                })
        
        return detected
    
    def can_capture(self):
        """Check if cooldown period has passed."""
        return (time.time() - self.last_capture_time) >= COOLDOWN_SECONDS
    
    def save_capture(self, img, objects):
        """Save image with detected objects."""
        if not self.can_capture():
            return False
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if objects:
            label = objects[0]["label"]
            conf = objects[0]["confidence"]
            filename = f"{timestamp}_{label}_{conf:.2f}.jpg"
        else:
            filename = f"{timestamp}_capture.jpg"
        
        # Save image
        filepath = SAVE_DIR / filename
        img.save(str(filepath))
        
        print(f"📸 Saved: {filename}")
        if objects:
            for obj in objects:
                print(f"   • {obj['label']}: {obj['confidence']:.2%}")
        
        self.last_capture_time = time.time()
        return True
    
    def draw_detections(self, img, objects):
        """Draw bounding boxes and labels on image."""
        for obj in objects:
            bbox = obj['bbox']
            label = obj['label']
            conf = obj['confidence']
            
            # Draw rectangle
            x1, y1, x2, y2 = map(int, bbox)
            img.draw_rectangle(x1, y1, x2-x1, y2-y1, color=(0, 255, 0), thickness=2)
            
            # Draw label
            text = f"{label} {conf:.2f}"
            img.draw_string(x1, y1-20, text, color=(0, 255, 0), scale=1.5)
        
        return img
    
    def run(self):
        """Main detection loop."""
        if not self.initialize():
            print("Initialization failed!")
            return
        
        print("Simple WildTrap running...")
        print(f"Target objects: {', '.join(TARGET_OBJECTS)}")
        print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}")
        print(f"Cooldown: {COOLDOWN_SECONDS}s")
        print(f"Saving to: {SAVE_DIR}")
        print("\nPress Ctrl+C to exit\n")
        
        try:
            while True:
                # Capture frame
                img = self.cam.read()
                if img is None:
                    continue
                
                # Step 1: Motion detection (fast)
                motion_detected = self.detect_motion(img)
                
                if motion_detected:
                    # Step 2: AI verification (slower but accurate)
                    objects = self.detect_objects(img)
                    
                    if objects:
                        print(f"🎯 Detection: {objects[0]['label']} ({objects[0]['confidence']:.2%})")
                        
                        # Step 3: Save capture
                        self.save_capture(img, objects)
                        
                        # Draw detections on display
                        img = self.draw_detections(img, objects)
                
                # Display frame
                if self.disp:
                    self.disp.show(img)
                
                # Small delay
                time.sleep(0.05)  # ~20 FPS
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Release resources."""
        if self.cam:
            del self.cam
        if self.disp:
            del self.disp
        print("Cleanup complete")


def main():
    """Entry point."""
    trap = SimpleWildTrap()
    trap.run()


if __name__ == "__main__":
    main()
