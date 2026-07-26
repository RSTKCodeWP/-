import subprocess import time
from urllib import response 
def ping_host(host): 
    response = subprocess.call( ['ping', '-c', '1', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
    return response == 0 
while True: status = ping_host("8.8.8.8") if status: print("Network Online") else: print("Network Offline") time.sleep(5)