from modules import Bcolors, clear_the_screen
import os


def net_hotspot_auto_11(config):
    while True:
        clear_the_screen()
        features_menu_content = """

             {bold} Automatic Hotspot / Wi-Fi setup{endc}


         Automatic hotspot will configure your timer to connect to any previously
         known Wi-Fi network if detected on startup.  

         If no known network is found, the timer will create a self-hosting hotspot
         that can be connected to on address: 10.0.0.5 (or <your_hostname>.local)

         The command 'autohotspot' will be available after install to re-detect Wi-Fi.
         
         Rebooting the timer will also cause it to re-detect know Wi-Fi networks 
         or create the hotspot (if known networks are not present). 



                     {green} y - Start auto hotspot config {endc}

                    {yellow} e - Exit to main menu {endc}

                 """.format(bold=Bcolors.BOLD_S, underline=Bcolors.UNDERLINE, endc=Bcolors.ENDC,
                            blue=Bcolors.BLUE, yellow=Bcolors.YELLOW_S, red=Bcolors.RED_S, green=Bcolors.GREEN_S)
        print(features_menu_content)
        selection = input()
        if selection == 'y':
            clear_the_screen()
            os.system(f"sudo /home/{config.user}/RH_Install-Manager/resources/autohotspot/setup_autohotspot.sh")
            print("""
                #######################################################################
                #                                                                     #
                # {bg}  Configuring auto hotspot is complete - service active{endc}   #
                #                                                                     #
                #              {bold}         Thank you!        {endc}                #
                #                                                                     #
                #######################################################################\n\n
                """.format(nodes_number=config.nodes_number, bold=Bcolors.BOLD_S,
                           bg=Bcolors.BOLD + Bcolors.GREEN + (' ' * 4), endc=Bcolors.ENDC_S))
            input("Press 'Enter' to continue")
            break
        elif selection == 'e':
            break
    pass


def main():
    net_hotspot_auto_11()


if __name__ == "__main__":
    main()
