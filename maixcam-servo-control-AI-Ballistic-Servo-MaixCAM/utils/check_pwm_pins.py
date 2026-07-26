"""
PWM Pin Checker for MaixCAM
Tests which PWM pins are available and working
"""

from maix import pinmap, pwm, err
import time

print("=" * 60)
print("PWM PIN CHECKER FOR MAIXCAM")
print("=" * 60)

# Common PWM pins on MaixCAM
PWM_PINS = [
    ("A18", 6),
    ("A19", 7),
    ("A20", 8),
    ("A21", 9),
    ("A22", 10),
    ("A23", 11),
]

print("\nTesting PWM pins...")
print("-" * 60)

working_pins = []
failed_pins = []

for pin_name, pwm_id in PWM_PINS:
    try:
        print(f"\nTesting {pin_name} (PWM{pwm_id})...")
        
        # Try to setup pin
        result = pinmap.set_pin_function(pin_name, f"PWM{pwm_id}")
        
        if result == 0:
            # Try to create PWM
            test_pwm = pwm.PWM(pwm_id, freq=50, duty=7.5, enable=True)
            
            # Test different duty cycles
            for duty in [2.5, 7.5, 12.5]:
                test_pwm.duty(duty)
                time.sleep(0.1)
            
            test_pwm.disable()
            
            working_pins.append((pin_name, pwm_id))
            print(f"✓ {pin_name} (PWM{pwm_id}) - WORKING")
        else:
            failed_pins.append((pin_name, pwm_id, "Setup failed"))
            print(f"✗ {pin_name} (PWM{pwm_id}) - SETUP FAILED")
    
    except Exception as e:
        failed_pins.append((pin_name, pwm_id, str(e)))
        print(f"✗ {pin_name} (PWM{pwm_id}) - ERROR: {e}")

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"\n✓ Working PWM pins ({len(working_pins)}):")
if working_pins:
    for pin_name, pwm_id in working_pins:
        print(f"  - {pin_name} (PWM{pwm_id})")
else:
    print("  None found")

print(f"\n✗ Failed PWM pins ({len(failed_pins)}):")
if failed_pins:
    for pin_name, pwm_id, reason in failed_pins:
        print(f"  - {pin_name} (PWM{pwm_id}): {reason}")
else:
    print("  None")

print("\n" + "=" * 60)
print("RECOMMENDATIONS")
print("=" * 60)

if working_pins:
    recommended = working_pins[0]
    print(f"\nRecommended pin: {recommended[0]} (PWM{recommended[1]})")
    print("\nUpdate your config:")
    print(f'  "servo_pin": "{recommended[0]}",')
    print(f'  "pwm_id": {recommended[1]},')
else:
    print("\n⚠️  No working PWM pins found!")
    print("Possible issues:")
    print("  1. Pins may be used by other peripherals")
    print("  2. Check MaixCAM documentation for your board version")
    print("  3. Try different pins manually")

print("\n" + "=" * 60)
print("SERVO CONNECTION GUIDE")
print("=" * 60)

if working_pins:
    pin_name, pwm_id = working_pins[0]
    print(f"\nConnect your servo:")
    print(f"  Servo Signal (yellow/white) -> {pin_name}")
    print(f"  Servo GND (brown/black)     -> GND")
    print(f"  Servo Power (red)           -> VBUS 5V")
    print("\n⚠️  Make sure your power supply provides enough current (500mA+)")

print("\n" + "=" * 60)
