from rpi_update import update
import os
import pwd
from modules import write_json, load_json, name_check
from compatibility_check import main as compatibility_check


def main():
    username = name_check()
    compatibility_check()
    passed_rh_ver = os.getenv('RH_VERSION')
    config_file = f"/home/{username}/RH_Install-Manager/updater-config.json"
    if os.path.exists(config_file):
        config = load_json(config_file)
        if passed_rh_ver in ['stable', 'beta', 'main']:
            config.rh_version = passed_rh_ver
            write_json(config, config_file)
        update(config, False)
    else:
        print("\n\n\t\tPlease install RotorHazard server first.\n\n"
              "\t\tType: './nh-install.sh 1'\n\n")


if __name__ == "__main__":
    main()
