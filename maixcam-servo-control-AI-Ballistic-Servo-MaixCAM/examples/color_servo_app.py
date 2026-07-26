from maix import camera, display, image, touchscreen, pinmap, pwm, err, app
import time as pytime
import json
import os

# ============ КОНФИГУРАЦИЯ ============
CONFIG_FILE = "/root/color_servo_config.json"
pin_name = "A18"
pwm_id = 6

# Настройка PWM
err.check_raise(pinmap.set_pin_function(pin_name, f"PWM{pwm_id}"), "PWM setup failed")

# Инициализация
cam = camera.Camera(1280, 720, image.Format.FMT_RGB888)
disp = display.Display()
ts = touchscreen.TouchScreen()
servo_pwm = pwm.PWM(pwm_id, freq=50, duty=2.5, enable=True)

# ============ СОСТОЯНИЕ ============
class State:
    def __init__(self):
        self.mode = "run"
        self.threshold = [[50, 80, 0, 30, 40, 80]]
        self.servo_opened = False
        self.open_time = 0
        self.close_delay = 10
        self.min_area = 300
        
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.threshold = data.get('threshold', self.threshold)
                    self.close_delay = data.get('close_delay', self.close_delay)
                    self.min_area = data.get('min_area', self.min_area)
                    print(f"Config loaded: {data}")
        except Exception as e:
            print(f"Config load error: {e}")
    
    def save_config(self):
        try:
            data = {
                'threshold': self.threshold,
                'close_delay': self.close_delay,
                'min_area': self.min_area
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            print(f"Config saved: {data}")
        except Exception as e:
            print(f"Config save error: {e}")

state = State()
state.load_config()

# ============ СЕРВО ============
def set_servo(angle):
    duty = 2.5 + (angle / 180.0) * 10.0
    servo_pwm.duty(duty)

def open_servo():
    set_servo(90)
    state.servo_opened = True
    state.open_time = pytime.time()
    print("SERVO OPEN")

def close_servo():
    set_servo(0)
    state.servo_opened = False
    print("SERVO CLOSE")

set_servo(0)
print("=== COLOR SERVO APP ===")
print(f"Servo: {pin_name} (PWM{pwm_id})")
print(f"Threshold: {state.threshold}")
print(f"Min area: {state.min_area}")

# ============ КАЛИБРОВКА ============
def get_lab_at_point(img, x, y, radius=20):
    """Получить средние LAB значения в области вокруг точки"""
    stats = img.get_statistics(roi=(x-radius, y-radius, radius*2, radius*2))
    return stats.l_mean(), stats.a_mean(), stats.b_mean()

def calibrate_color(img, x, y):
    """Калибровка цвета по клику"""
    l, a, b = get_lab_at_point(img, x, y, radius=25)
    
    # Создаем пороги с большим запасом для надежности
    l_min = max(0, int(l - 20))
    l_max = min(100, int(l + 20))
    a_min = max(-128, int(a - 25))
    a_max = min(127, int(a + 25))
    b_min = max(-128, int(b - 25))
    b_max = min(127, int(b + 25))
    
    state.threshold = [[l_min, l_max, a_min, a_max, b_min, b_max]]
    state.save_config()
    
    print(f"Calibrated: LAB=({l:.0f}, {a:.0f}, {b:.0f})")
    print(f"Threshold: {state.threshold}")
    return l, a, b

# ============ ГЛАВНЫЙ ЦИКЛ ============
frame_count = 0
fps_time = pytime.time()
fps = 0

while not app.need_exit():
    img = cam.read()
    
    # FPS
    frame_count += 1
    if frame_count % 30 == 0:
        now = pytime.time()
        fps = 30 / (now - fps_time)
        fps_time = now
    
    # Обработка тачскрина
    touch_data = ts.read()
    if touch_data:
        x, y, pressed = touch_data
        
        if pressed:
            # Масштабирование координат
            img_w, img_h = img.width(), img.height()
            disp_w, disp_h = disp.width(), disp.height()
            x = int(x * img_w / disp_w)
            y = int(y * img_h / disp_h)
            
            if state.mode == "run":
                state.mode = "calibrate"
                print("CALIBRATION MODE")
            else:
                l, a, b = calibrate_color(img, x, y)
                # Показываем большой круг где калибровали
                img.draw_circle(x, y, 30, color=image.Color.from_rgb(255, 0, 255), thickness=4)
                state.mode = "run"
                print("RUN MODE")
    
    # Поиск цветных областей
    blobs = img.find_blobs(state.threshold, 
                           pixels_threshold=state.min_area,
                           area_threshold=state.min_area,
                           merge=True)
    
    # Управление серво
    current_time = pytime.time()
    if state.servo_opened and (current_time - state.open_time >= state.close_delay):
        close_servo()
    
    if blobs and not state.servo_opened:
        largest = max(blobs, key=lambda b: b[2] * b[3])
        open_servo()
    
    # Отрисовка
    for blob in blobs:
        x, y, w, h = blob[0], blob[1], blob[2], blob[3]
        area = w * h
        
        if area > state.min_area * 3:
            color = image.Color.from_rgb(0, 255, 0)
        else:
            color = image.Color.from_rgb(255, 255, 0)
        
        img.draw_rect(x, y, w, h, color=color, thickness=2)
        img.draw_string(x, y - 10, f"{area}", color=color)
    
    # UI - увеличенный шрифт
    servo_status = "OPEN" if state.servo_opened else "CLOSED"
    servo_color = image.Color.from_rgb(0, 255, 0) if state.servo_opened else image.Color.from_rgb(255, 255, 255)
    
    # Основной статус - крупно
    img.draw_string(10, 10, f"SERVO: {servo_status}", color=servo_color, scale=3)
    
    # Инфо - средний размер
    img.draw_string(10, 60, f"FPS: {fps:.1f}", color=image.Color.from_rgb(255, 255, 255), scale=2)
    img.draw_string(10, 90, f"Blobs: {len(blobs)}", color=image.Color.from_rgb(255, 255, 255), scale=2)
    
    if state.servo_opened:
        remaining = int(state.close_delay - (current_time - state.open_time))
        img.draw_string(10, 120, f"Close: {remaining}s", color=image.Color.from_rgb(255, 255, 0), scale=2)
    
    # Подсказка внизу - крупно
    if state.mode == "calibrate":
        img.draw_string(10, img.height() - 50, "TAP TARGET COLOR", 
                       color=image.Color.from_rgb(255, 0, 255), scale=3)
    else:
        img.draw_string(10, img.height() - 50, "TAP TO CALIBRATE", 
                       color=image.Color.from_rgb(150, 150, 150), scale=2)
    
    disp.show(img)

# Cleanup
close_servo()
servo_pwm.disable()
cam.close()
print("EXIT")
