from maix import pinmap, pwm, err
import time

# Настройка PWM
pin_name = "A18"
pwm_id = 6

print(f"Testing servo on {pin_name} (PWM{pwm_id})")
print("Connecting servo:")
print("  Signal -> A18")
print("  GND -> GND")
print("  Power -> VBUS 5V")

# Установка функции пина на PWM
err.check_raise(pinmap.set_pin_function(pin_name, f"PWM{pwm_id}"), "PWM setup failed")

# Создание PWM (50Hz для серво)
servo = pwm.PWM(pwm_id, freq=50, duty=7.5, enable=True)

print("\n=== SERVO TEST START ===")
print("Watch the servo motor...")

# Тест разных углов
angles = [0, 45, 90, 135, 180, 90, 0]

for angle in angles:
    duty = 2.5 + (angle / 180.0) * 10.0
    servo.duty(duty)
    print(f"Angle: {angle:3d}° | Duty: {duty:5.2f}% | Pulse: {duty*0.2:.2f}ms")
    time.sleep(1)

print("\n=== TEST COMPLETE ===")
print("Did the servo move? (yes/no)")
print("If NO:")
print("  1. Check A18 connection")
print("  2. Check power: VBUS 5V must provide enough current")
print("  3. Try different servo or check if it's broken")
print("  4. Measure voltage on servo power wire")

servo.disable()
