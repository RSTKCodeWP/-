from maix import camera, display, image, touchscreen, pinmap, pwm, err, app
import time as pytime
import json
import os

# ============ КОНФИГУРАЦИЯ ============
CONFIG_FILE = "/root/servo_detector_config.json"
pin_name = "A18"
pwm_id = 6

err.check_raise(pinmap.set_pin_function(pin_name, f"PWM{pwm_id}"), "PWM setup")

cam = camera.Camera(640, 480, image.Format.FMT_RGB888)
disp = display.Display()
ts = touchscreen.TouchScreen()
servo_pwm = pwm.PWM(pwm_id, freq=50, duty=2.5, enable=True)

# ============ ПРЕСЕТЫ ============
PRESETS = {
    "Yellow": [[50, 80, 0, 30, 40, 80]],
    "Red": [[0, 80, 40, 80, 10, 80]],
    "Green": [[0, 80, -120, -10, 0, 30]],
    "Blue": [[0, 80, 30, 100, -120, -60]],
    "Custom": [[50, 80, 0, 30, 40, 80]]
}

# ============ СОСТОЯНИЕ ============
class AppState:
    def __init__(self):
        self.mode = "color"  # color, object, motion
        self.preset = "Yellow"
        self.threshold = PRESETS["Yellow"]
        self.servo_opened = False
        self.open_time = 0
        self.close_delay = 10
        self.min_area = 500
        self.sensitivity = 50
        self.ui_mode = "run"  # run, menu, calibrate
        self.prev_frame = None
        
    def load(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.mode = data.get('mode', self.mode)
                    self.preset = data.get('preset', self.preset)
                    self.threshold = data.get('threshold', self.threshold)
                    self.close_delay = data.get('close_delay', self.close_delay)
                    self.min_area = data.get('min_area', self.min_area)
                    self.sensitivity = data.get('sensitivity', self.sensitivity)
                    print(f"Loaded: {data}")
        except Exception as e:
            print(f"Load error: {e}")
    
    def save(self):
        try:
            data = {
                'mode': self.mode,
                'preset': self.preset,
                'threshold': self.threshold,
                'close_delay': self.close_delay,
                'min_area': self.min_area,
                'sensitivity': self.sensitivity
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            print(f"Saved: {data}")
        except Exception as e:
            print(f"Save error: {e}")

state = AppState()
state.load()

# ============ СЕРВО ============
def set_servo(angle):
    duty = 2.5 + (angle / 180.0) * 10.0
    servo_pwm.duty(duty)

def open_servo():
    set_servo(90)
    state.servo_opened = True
    state.open_time = pytime.time()

def close_servo():
    set_servo(0)
    state.servo_opened = False

set_servo(0)

# ============ ДЕТЕКТОРЫ ============
def detect_color(img):
    """Детекция по цвету"""
    blobs = img.find_blobs(state.threshold, 
                           pixels_threshold=state.min_area,
                           area_threshold=state.min_area,
                           merge=True)
    return len(blobs) > 0, blobs

def detect_object(img):
    """Детекция любого объекта (контуры)"""
    edges = img.find_edges(image.EDGE_CANNY, threshold=(50, 100))
    blobs = edges.find_blobs([[0, 100, -128, 127, -128, 127]], 
                             pixels_threshold=state.min_area * 2,
                             area_threshold=state.min_area * 2)
    return len(blobs) > 0, blobs

def detect_motion(img):
    """Детекция движения"""
    if state.prev_frame is None:
        state.prev_frame = img.copy()
        return False, []
    
    diff = img.difference(state.prev_frame)
    stats = diff.get_statistics()
    
    # Обновляем предыдущий кадр
    state.prev_frame = img.copy()
    
    # Если среднее изменение больше порога
    motion_detected = stats.l_mean() > state.sensitivity
    return motion_detected, []

# ============ КАЛИБРОВКА ============
def calibrate_color(img, x, y):
    stats = img.get_statistics(roi=(x-25, y-25, 50, 50))
    l, a, b = stats.l_mean(), stats.a_mean(), stats.b_mean()
    
    l_min = max(0, int(l - 20))
    l_max = min(100, int(l + 20))
    a_min = max(-128, int(a - 25))
    a_max = min(127, int(a + 25))
    b_min = max(-128, int(b - 25))
    b_max = min(127, int(b + 25))
    
    state.threshold = [[l_min, l_max, a_min, a_max, b_min, b_max]]
    state.preset = "Custom"
    PRESETS["Custom"] = state.threshold
    state.save()
    print(f"Calibrated: LAB=({l:.0f},{a:.0f},{b:.0f})")

# ============ UI КНОПКИ ============
class Button:
    def __init__(self, x, y, w, h, text, action):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.text = text
        self.action = action
    
    def draw(self, img, active=False):
        color = image.Color.from_rgb(0, 255, 0) if active else image.Color.from_rgb(255, 255, 255)
        img.draw_rect(self.x, self.y, self.w, self.h, color=color, thickness=2)
        img.draw_string(self.x + 5, self.y + 5, self.text, color=color, scale=1.5)
    
    def is_clicked(self, x, y):
        return self.x < x < self.x + self.w and self.y < y < self.y + self.h

# Создаем кнопки меню
menu_buttons = [
    Button(10, 60, 150, 40, "COLOR", lambda: setattr(state, 'mode', 'color')),
    Button(10, 110, 150, 40, "OBJECT", lambda: setattr(state, 'mode', 'object')),
    Button(10, 160, 150, 40, "MOTION", lambda: setattr(state, 'mode', 'motion')),
    Button(10, 220, 150, 40, "Yellow", lambda: (setattr(state, 'preset', 'Yellow'), setattr(state, 'threshold', PRESETS['Yellow']))),
    Button(10, 270, 150, 40, "Red", lambda: (setattr(state, 'preset', 'Red'), setattr(state, 'threshold', PRESETS['Red']))),
    Button(10, 320, 150, 40, "Green", lambda: (setattr(state, 'preset', 'Green'), setattr(state, 'threshold', PRESETS['Green']))),
    Button(10, 370, 150, 40, "Custom", lambda: setattr(state, 'ui_mode', 'calibrate')),
    Button(10, 430, 150, 40, "SAVE", lambda: state.save()),
]

# ============ ГЛАВНЫЙ ЦИКЛ ============
fps, frame_count, fps_time = 0, 0, pytime.time()

print("=== SERVO DETECTOR APP ===")
print(f"Mode: {state.mode}, Preset: {state.preset}")

while not app.need_exit():
    img = cam.read()
    
    # FPS
    frame_count += 1
    if frame_count % 30 == 0:
        fps = 30 / (pytime.time() - fps_time)
        fps_time = pytime.time()
    
    # Тачскрин
    touch_data = ts.read()
    if touch_data:
        tx, ty, pressed = touch_data
        if pressed:
            if state.ui_mode == "menu":
                # Проверка кликов по кнопкам
                for btn in menu_buttons:
                    if btn.is_clicked(tx, ty):
                        btn.action()
                        if btn.text == "SAVE":
                            state.ui_mode = "run"
                        break
            elif state.ui_mode == "calibrate":
                # Калибровка цвета
                img_w, img_h = img.width(), img.height()
                disp_w, disp_h = disp.width(), disp.height()
                x = int(tx * img_w / disp_w)
                y = int(ty * img_h / disp_h)
                calibrate_color(img, x, y)
                img.draw_circle(x, y, 30, color=image.Color.from_rgb(255, 0, 255), thickness=4)
                state.ui_mode = "run"
            else:
                # Открыть меню
                state.ui_mode = "menu"
    
    # Детекция
    detected = False
    blobs = []
    
    if state.ui_mode == "run":
        if state.mode == "color":
            detected, blobs = detect_color(img)
        elif state.mode == "object":
            detected, blobs = detect_object(img)
        elif state.mode == "motion":
            detected, blobs = detect_motion(img)
        
        # Управление серво
        current_time = pytime.time()
        if state.servo_opened and (current_time - state.open_time >= state.close_delay):
            close_servo()
        
        if detected and not state.servo_opened:
            open_servo()
        
        # Отрисовка детекций
        for blob in blobs:
            x, y, w, h = blob[0], blob[1], blob[2], blob[3]
            img.draw_rect(x, y, w, h, color=image.Color.from_rgb(0, 255, 0), thickness=2)
    
    # UI
    if state.ui_mode == "menu":
        # Затемнение фона
        img.draw_rect(0, 0, 200, img.height(), color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        
        # Заголовок
        img.draw_string(10, 10, "MENU", color=image.Color.from_rgb(255, 255, 0), scale=3)
        
        # Кнопки
        for btn in menu_buttons:
            active = False
            if btn.text == state.mode.upper():
                active = True
            elif btn.text == state.preset:
                active = True
            btn.draw(img, active)
    
    elif state.ui_mode == "calibrate":
        img.draw_string(10, img.height() - 50, "TAP TARGET COLOR", 
                       color=image.Color.from_rgb(255, 0, 255), scale=3)
    
    else:  # run mode
        # Статус
        status = "OPEN" if state.servo_opened else "CLOSED"
        color = image.Color.from_rgb(0, 255, 0) if state.servo_opened else image.Color.from_rgb(255, 255, 255)
        img.draw_string(10, 10, f"{status}", color=color, scale=3)
        
        # Инфо
        img.draw_string(10, 60, f"{state.mode.upper()}/{state.preset}", 
                       color=image.Color.from_rgb(255, 255, 255), scale=2)
        img.draw_string(10, 90, f"FPS:{fps:.0f}", 
                       color=image.Color.from_rgb(255, 255, 255), scale=2)
        
        if state.servo_opened:
            remaining = int(state.close_delay - (pytime.time() - state.open_time))
            img.draw_string(10, 120, f"Close:{remaining}s", 
                           color=image.Color.from_rgb(255, 255, 0), scale=2)
        
        # Подсказка
        img.draw_string(10, img.height() - 40, "TAP FOR MENU", 
                       color=image.Color.from_rgb(150, 150, 150), scale=2)
    
    disp.show(img)

# Cleanup
close_servo()
servo_pwm.disable()
cam.close()
