import json
import os
from pathlib import Path
from time import sleep
from modules import clear_the_screen, logo_top, show_ip


def conf_check():
    home_dir = str(Path.home())
    conf_now_flag = 1
    ethernet_ip, wlan_ip = show_ip()

    ap_config = {}  # Initialize ap_config as an empty dictionary

    if os.path.exists(f"{home_dir}/RH_Install-Manager/ap-config.json"):
        with open(f"{home_dir}/RH_Install-Manager/ap-config.json", "r") as json_file:
            ap_config = json.load(json_file)

        ssid = ap_config.get("WIFI", {}).get("SSID")
        password = ap_config.get("WIFI", {}).get("PASSWORD")
        ethernet_ip, wlan_ip = show_ip()

        print(f"""\n
        Looks like you have AccessPoint already configured.
              
              Current configuration:
              
        Ethernet IP: {ethernet_ip}
        Hotspot IP:  {wlan_ip}
        SSID (hotspot name): {ssid}
        Password (password): {password}
        \n\n""")

        while True:
            cont_conf = input("\tOverwrite and continue anyway? [Y/n]\t\t").lower()
            if not cont_conf:
                print("Answer defaulted to: yes")
                break
            elif cont_conf[0] == 'y':
                conf_now_flag = True
                break
            elif cont_conf[0] == 'n':
                conf_now_flag = False
                break
            else:
                print("\nPlease enter correct value")

    else:
        while True:
            print("""
            
        Please note that this action will disable Wi-Fi client mode 
        on your Raspberry.
            """)
            print(f"""
        Current configuration:
        Ethernet IP: {ethernet_ip}
        Wi-Fi IP:    {wlan_ip}\n""")
            confirm_conf = input("""
        Do you want to continue? [Y/n]\t\t""").lower()
            if not confirm_conf:
                print("Answer defaulted to: yes")
                break
            elif confirm_conf[0] == 'y':
                conf_now_flag = True
                break
            elif confirm_conf[0] == 'n':
                conf_now_flag = False
                break
            else:
                print("\nPlease enter correct value")

    return conf_now_flag


def save_config_os(ssid, password):
    os.system(
        "sudo nmcli connection delete $(sudo nmcli -t -f NAME,TYPE con show | awk -F: '/:802-11-wireless$/ {print $1}') > /dev/null 2>&1")
    os.system(f"sudo nmcli con add con-name hotspot ifname wlan0 type wifi ssid {ssid}")
    os.system(f"sudo nmcli con modify hotspot wifi-sec.key-mgmt wpa-psk")
    os.system(f"sudo nmcli con modify hotspot wifi-sec.psk '{password}'")
    os.system(f"sudo nmcli con modify hotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared")
    print("\n\n\tHotspot configuration data has been saved\n")
    sleep(3)


def do_config():
    clear_the_screen()
    logo_top(False)

    home_dir = str(Path.home())
    conf_now_flag = conf_check()

    if conf_now_flag:
        clear_the_screen()
        logo_top(False)
        ap_config = {}

        print("""\n\t\t\tEnter hotspot configuration:\n""")

        ssid = input("\n\t\tEnter SSID (hotspot name):          ")
        ap_config["WIFI"] = {"SSID": ssid}

        while True:
            password = input("\n\t\tEnter Password (min. 8 characters): ")
            if len(password) < 8:
                print("\n\t\tPassword should be at least 8 characters long")
            else:
                break

        ap_config["WIFI"]["PASSWORD"] = password

        ap_configuration_summary = f"""\n\n
            WIFI SSID:          {ap_config["WIFI"]["SSID"]}
            WIFI Password:      {ap_config["WIFI"]["PASSWORD"]}

            Please check. Confirm? [yes/change/abort]\n"""
        print(ap_configuration_summary)

        valid_options = ['y', 'yes', 'n', 'no', 'change', 'abort']
        while True:
            selection = input().strip()
            if selection in valid_options:
                break
            else:
                print("\nPlease enter correct value")
        if selection[0] == 'y':
            with open(f"{home_dir}/RH_Install-Manager/ap-config.json", "w") as json_file:
                json.dump(ap_config, json_file, indent=4)
            save_config_os(ssid, password)
            clear_the_screen()
            logo_top(False)
            ethernet_ip, wlan_ip = show_ip()
            print(f"""\n\n
            Current configuration: 

            Ethernet IP: {ethernet_ip}
            Hotspot IP:  {wlan_ip}
            SSID (hotspot name): {ssid}
            Password (password): {password}\n\n""")

            input("\n\tHit Enter to exit this screen")
            conf_now_flag = 0
        if selection in ['change', 'n', 'no']:
            conf_now_flag = 1
        if selection == 'abort':
            print("Configuration aborted.\n")
            sleep(0.5)
            conf_now_flag = 0

    return conf_now_flag


def net_hotspot_manual_12():
    config_now = 1
    while config_now:
        config_now = do_config()


def main():
    net_hotspot_manual_12()


if __name__ == "__main__":
    main()
