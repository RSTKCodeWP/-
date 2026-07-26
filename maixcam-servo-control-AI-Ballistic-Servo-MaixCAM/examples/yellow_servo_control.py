from maix import camera, display, image, time, pinmap, pwm, err, sys
import time as pytime

# Настройка PWM пина для сервопривода
pin_name = "A18"
pwm_id = 6

# Установка функции пина на PWM
err.check_raise(pinmap.set_pin_function(pin_name, f"PWM{pwm_id}"), "PWM pinmap setup failed")

# Инициализация камеры
cam = camera.Camera(640, 480, image.Format.FMT_RGB888)

# Инициализация дисплея
disp = display.Display()

# Настройка PWM для сервопривода (50 Hz для серво)
servo_pwm = pwm.PWM(pwm_id, freq=50, duty=7.5, enable=True)

# Пороги для желтого цвета в LAB
# Формат: [L_MIN, L_MAX, A_MIN, A_MAX, B_MIN, B_MAX]
# Желтый: яркий, небольшой положительный A, высокий положительный B
# Более строгие пороги чтобы не реагировать на кожу
yellow_threshold = [[50, 80, 0, 30, 40, 80]]

# Флаг состояния сервопривода
servo_opened = False
open_time = 0

def set_servo_angle(angle):
    """Установка угла сервопривода (0-180°)"""
    duty = 2.5 + (angle / 180.0) * 10.0
    servo_pwm.duty(duty)
    print(f"Servo: {angle}° (duty: {duty:.2f}%)")

def open_servo():
    """Открыть сервопривод"""
    set_servo_angle(90)

def close_servo():
    """Закрыть сервопривод"""
    set_servo_angle(0)

# Тест серво при запуске
print("=== SERVO TEST ===")
set_servo_angle(0)
pytime.sleep(1)
set_servo_angle(90)
pytime.sleep(1)
set_servo_angle(0)
pytime.sleep(0.5)
print("=== TEST COMPLETE ===")
print(f"Servo on {pin_name} (PWM{pwm_id})")
print(f"Yellow threshold: {yellow_threshold}")

while True:
    img = cam.read()
    
    # Поиск желтых областей (find_blobs автоматически конвертирует в LAB)
    blobs = img.find_blobs(yellow_threshold, 
                           pixels_threshold=500,
                           area_threshold=500)
    
    # Проверка таймера для автоматического закрытия
    current_time = pytime.time()
    if servo_opened and (current_time - open_time >= 10):
        close_servo()
        servo_opened = False
    
    # Обработка обнаруженных желтых объектов
    if blobs and not servo_opened:
        open_servo()
        servo_opened = True
        open_time = current_time
        print(f"YELLOW DETECTED! Blobs: {len(blobs)}")
    
    # Отрисовка результатов
    for blob in blobs:
        x, y, w, h = blob[0], blob[1], blob[2], blob[3]
        img.draw_rect(x, y, w, h, color=image.Color.from_rgb(255, 0, 0), thickness=2)
        img.draw_string(x, y - 10, "YELLOW", color=image.Color.from_rgb(255, 0, 0))
    
    # Статус на экране
    status = "OPEN" if servo_opened else "CLOSED"
    color = image.Color.from_rgb(0, 255, 0) if servo_opened else image.Color.from_rgb(255, 255, 255)
    img.draw_string(10, 10, f"SERVO: {status}", color=color, scale=2)
    
    if servo_opened:
        remaining = int(10 - (current_time - open_time))
        img.draw_string(10, 40, f"Close in: {remaining}s", 
                       color=image.Color.from_rgb(255, 255, 0))
    
    disp.show(img)
