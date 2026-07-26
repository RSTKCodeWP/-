import os
import platform
from pathlib import Path
import json


# removes old aliases, especially doubled ones and bad leftovers from ~/.bashrc file

def aliases_clean(start, end, file_name, *words):
    if platform.system() == "Linux":
        write_lines = []
        skipping = False
        with open(file_name, 'r') as read_obj:
            for line in read_obj:
                if start in line:
                    skipping = True
                if not skipping:
                    write_lines.append(line)
                if end in line:
                    skipping = False
                for word in words:
                    if word in line:
                        write_lines.remove(line)

        with open(file_name, 'w') as write_obj:
            write_obj.write("".join(write_lines))
            return False


def virtual_env_check(file_path, word):
    with open(file_path, 'r') as file:
        content = file.read()
        if word in content:
            print('virtual env in .bashrc already setup')
        else:
            os.system("echo 'VIRTUAL_ENV_DISABLE_PROMPT=1' >> ~/.bashrc")
            os.system("echo 'source ~/.venv/bin/activate' >> ~/.bashrc")


def json_user_change(home_dir):
    config_file = f"{home_dir}/RH_Install-Manager/updater-config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            data = json.load(file)

        if 'pi_user' in data:
            pi_user_value = data['pi_user']
            data['user'] = pi_user_value

        with open(config_file, 'w') as file:
            json.dump(data, file, indent=2)


def main():
    home_dir = str(Path.home())
    Path(f"{home_dir}/.rhim_markers").mkdir(exist_ok=True)
    aliases_clean('Shortcut', 'After', f'{home_dir}/.bashrc', 'uu', 'updateupdater', '# #')
    virtual_env_check(f'{home_dir}/.bashrc', 'VIRTUAL_ENV_DISABLE_PROMPT')
    json_user_change(home_dir)


if __name__ == "__main__":
    main()
