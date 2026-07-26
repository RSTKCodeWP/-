import os

from modules import rhim_load_config, clear_the_screen, logo_top, Bcolors
from net_hotspot_manual_12 import net_hotspot_manual_12
from net_hotspot_auto_12 import net_hotspot_auto_12
from net_hotspot_manual_11 import net_hotspot_manual_11
from net_hotspot_auto_11 import net_hotspot_auto_11


def show_os_info(config):
    clear_the_screen()
    logo_top(config.debug_mode)
    print("\n\n")
    os.system("cat /sys/firmware/devicetree/base/model")
    print("\n")
    os.system("cat /etc/os-release")
    print("\n\n")
    input("Hit 'Enter' to exit")


def net_menu(config):
    while True:
        clear_the_screen()
        logo_top(config.debug_mode)
        features_menu_content = """

                        {rmh}NETWORKING MENU (choose right OS){endc}{bold}

                            
                1 - Setup automatic hotspot/Wi-Fi   (Bookworm)
                
                2 - Setup hotspot - always on       (Bookworm)
                
                3 - Setup automatic hotspot/Wi-Fi   (Bullseye)

                4 - Setup hotspot - always on       (Bullseye)
                
                5 - Show my Raspberry Pi OS information

        {yellow}e - Exit to main menu {endc}

                 """.format(rmh=Bcolors.RED_MENU_HEADER, yellow=Bcolors.YELLOW_S, bold=Bcolors.BOLD, endc=Bcolors.ENDC)
        print(features_menu_content)
        selection = input()
        if selection == '1':
            net_hotspot_auto_12()
        elif selection == '2':
            net_hotspot_manual_12()
        elif selection == '3':
            net_hotspot_auto_11(config)
        elif selection == '4':
            net_hotspot_manual_11(config)
        elif selection == '5':
            show_os_info(config)
        elif selection == 'e':
            break
    pass


def main():
    config = rhim_load_config()
    net_menu(config)


if __name__ == "__main__":
    main()
