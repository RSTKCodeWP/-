import os
from time import sleep

# import shutil
from modules import rhim_load_config, dots_show, internet_check, get_rhim_version, Bcolors


def make_directories_accessible(config):
    markers_dir = f'/home/{config.user}/.rhim_markers'
    rhim_dir = f'/home/{config.user}/RH_Install-Manager'
    os.system(f"sudo chmod -R 777 {markers_dir} > /dev/null 2>&1") if os.stat(markers_dir).st_uid == 0 else None
    os.system(f"sudo chmod -R 777 {rhim_dir} > /dev/null 2>&1") if os.stat(rhim_dir).st_uid == 0 else None


def self_update(config):
    internet_flag = internet_check()
    if not internet_flag:
        print(f"\t{Bcolors.RED}Looks like you don't have internet connection.{Bcolors.ENDC}")
        sleep(0.5)
        os.system("./scripts/net_fixer.sh")
        print("Trying again...")
        internet_flag = internet_check()
    if not internet_flag:  # don't change to 'elif' - it is second check after a repair!
        print(f"\t{Bcolors.RED}Looks like you still don't have internet connection. Update canceled.{Bcolors.ENDC}")
        sleep(2)
    else:
        print(f"\t\t{Bcolors.GREEN}Internet connection - OK{Bcolors.ENDC}\n")
        sleep(1.5)
        make_directories_accessible(config)
        old_version_name = get_rhim_version(True)
        print(f"\n\n\n\t Please wait: updating process from version {old_version_name}\n\n")
        dots_show(2)
        # if config:  # if config is not empty, then the file exited to load.
        #     shutil.copyfile('~/RH_Install-Manager/updater-config.json', '~/.rhim_markers/updater-config.json')
        if config.beta_tester is True:
            source = 'dev'
            print("This will be the 'beta' update - may be changed in config wizard.\n")
        elif config.beta_tester is False:
            source = 'stable'
        else:
            source = config.beta_tester
        os.system(f"./scripts/self_updater.sh {source}")
        # if config:  # if the config variable is not empty, then the config file must have existed.
        #   shutil.copyfile("~/.rhim_markers/old_RH_Install-Manager/updater-config.json", "~/RH_Install-Manager/updater-config.json")
        new_version_name = get_rhim_version(True)
        print(f"""
        
        RotorHazard Manager updated to version {new_version_name}
        
                You can check update-notes.
    
                """)
        sleep(1)
        make_directories_accessible(config)
        os.system(
            "cp ~/.rhim_markers/old_RH_Install-Manager/updater-config.json ~/RH_Install-Manager/updater-config.json "
            " > /dev/null 2>&1")
        os.system(
            "cp ~/.rhim_markers/old_RH_Install-Manager/ap-config.json ~/RH_Install-Manager/ap-config.json "
            " > /dev/null 2>&1")
        # it had some bug with shutil - can be changed when resolved
        if new_version_name != old_version_name:
            os.system("echo RHIM was updated > ~/.rhim_markers/.was_updated_new")
        else:
            os.system("echo RHIM was not updated > ~/.rhim_markers/.was_updated_old")


def main():
    config = rhim_load_config()
    self_update(config)


if __name__ == "__main__":
    main()
