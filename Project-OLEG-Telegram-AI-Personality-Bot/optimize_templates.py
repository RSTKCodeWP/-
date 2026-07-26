import os
import subprocess
import shutil
import glob

TEMPLATES_DIR = "assets/video_templates"
BACKUP_DIR = "assets/video_templates/backup"

def get_video_info(file_path):
    """Returns width, height, fps"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0", file_path
        ]
        output = subprocess.check_output(cmd).decode().strip().split(',')
        width = int(output[0])
        height = int(output[1])
        fps_parts = output[2].split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(output[2])
        return width, height, fps
    except Exception as e:
        print(f"Error probing {file_path}: {e}")
        return None

def optimize_template(file_path):
    filename = os.path.basename(file_path)
    info = get_video_info(file_path)
    
    if not info:
        return
        
    width, height, fps = info
    
    # Check if optimization is needed
    if width == 640 and height == 640 and abs(fps - 24.0) < 0.1:
        print(f"✅ {filename} is already optimized (640x640, {fps:.2f}fps)")
        return

    print(f"🔄 Optimizing {filename} ({width}x{height}, {fps:.2f}fps) -> (640x640, 24fps)...")
    
    # Create backup
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
    
    # Temporary output file
    temp_output = file_path + ".temp.mp4"
    
    # FFmpeg command to resize/crop to 640x640 central crop
    # Using scale to cover 640x640 then crop
    cmd = [
        "ffmpeg", "-y", "-i", file_path,
        "-vf", "scale=640:640:force_original_aspect_ratio=increase,crop=640:640,setsar=1,fps=24",
        "-c:v", "libx264",
        "-preset", "slow", # Use slow preset for better quality since this is one-time
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an", # Remove audio from template
        temp_output
    ]
    
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(temp_output, file_path)
        print(f"✨ {filename} optimized successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to optimize {filename}: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)

def main():
    print("🚀 Starting template optimization...")
    
    files = glob.glob(os.path.join(TEMPLATES_DIR, "*.mp4"))
    if not files:
        print("No templates found.")
        return

    for file_path in files:
        # Skip backup dir files if glob picked them up (it shouldn't with *.mp4 but being safe)
        if "backup" in file_path:
            continue
            
        optimize_template(file_path)
        
    print("🎉 All done!")

if __name__ == "__main__":
    main()
