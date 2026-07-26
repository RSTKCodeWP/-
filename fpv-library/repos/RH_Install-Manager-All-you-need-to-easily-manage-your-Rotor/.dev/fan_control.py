import subprocess
import os
from time import sleep

os.system("pinctrl set 4 op")


def get_cpu_temperature():
    res = subprocess.check_output(["vcgencmd", "measure_temp"]).decode("utf-8")
    temp = float(res.replace("temp=", "").replace("'C\n", ""))
    #    print(temp)
    return temp


try:

    while True:
        # Get CPU temperature
        cpu_temp = get_cpu_temperature()

        # Calculate duty cycle based on CPU temperature
        if cpu_temp < 50:
            os.system("pinctrl set 4 dl")
            print("state1")
            sleep(60)
        elif cpu_temp >= 50 and cpu_temp < 55:
            os.system("pinctrl set 4 dh")
            sleep(0.006)
            os.system("pinctrl set 4 dl")
            sleep(0.01 - 0.006)
            print("state2")
        elif cpu_temp >= 55 and cpu_temp < 60:
            os.system("pinctrl set 4 dh")
            sleep(0.007)
            os.system("pinctrl set 4 dl")
            sleep(0.01 - 0.007)
            print("state3")
        elif cpu_temp >= 60 and cpu_temp < 65:
            os.system("pinctrl set 4 dh")
            sleep(0.008)
            os.system("pinctrl set 4 dl")
            sleep(0.01 - 0.008)
            print("state4")
        elif cpu_temp >= 65 and cpu_temp < 70:
            os.system("pinctrl set 4 dh")
            sleep(0.009)
            os.system("pinctrl set 4 dl")
            sleep(0.01 - 0.009)
            print("state5")
        else:
            os.system("pinctrl set 4 dh")
            print("state6")

        print(cpu_temp)


except KeyboardInterrupt:
    # Clean up GPIO pin
    write_pin_value(fan_pin, 0)
    set_pin_mode(fan_pin, "in")
