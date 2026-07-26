#!/bin/python3

import argparse
import re
import tailer
import array
import itertools
import numpy as np
#import matplotlib.pyplot as plt
import threading
from time import sleep
import os
import subprocess

#Data from wfb_cli
#file.writelines("An"+str(y)+" "+str(rssi_avg)+" "+str(snr_avg)+" "+str(rssi_min)+" "+str(p['fec_rec'][0])+" "+str(p['lost'][0])+"\n")

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", help="Specify input file", default="/home/deck/testfile")
parser.add_argument("-o", "--output", help="Where to send output", default="/dev/pts/5")
parser.add_argument("-v", "--verbosity", action="count", default=0)
args = parser.parse_args()

if args.verbosity >= 2:
    print("Super extra verbose")

if args.verbosity >= 1:
    print("Extra verbose")

#default 0 verbose
#print("dEFAULT Always hello")
print(args.input)

def runCommand (command):
    output=subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    if output.returncode != 0:
        raise RuntimeError(
            output.stderr.decode("utf-8"))

    return output


a = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
b = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
c = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
d = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
e = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
f = array_of_signed_ints = array.array("i", itertools.repeat(0, 10))
def start_reading():
    for line in tailer.follow(open(args.input)):
        splitLines = line.split()
        a.append(int(splitLines[0]))
        b.append(int(splitLines[1]))
        c.append(int(splitLines[2]))
        d.append(int(splitLines[3]))
        e.append(int(splitLines[4]))
        f.append(int(splitLines[5]))
        #Debug
        #print("READING NEW DATA")


readThread = threading.Thread(target = start_reading)
readThread.daemon = True
readThread.start()


def normalizeData(input, max, min):
    if input < min:
        return -1024
    if input > max:
        #print("test")
        return 1024
    return int(-1024+((input - min) / (max - min)*2048))


counter=0
while True:
  counter += 1
  print("Main thread " + str(counter))

  #take read_buf latest avg_rssi readings, select the highest n readings and calculate their average, regardless of antenna
  read_buf = 4
  n = 2
  l_b = b[-read_buf:].tolist()
  l_b.sort()
  #rssi_data = np.mean(l_b[-n:])
  rssi_data = np.median(l_b)
  print(str(rssi_data))

  #take read_buf latest avg_snr readings, select the highest n readings and calculate their average, regardless of antenna
  read_buf = 4
  n = 2
  l_c = c[-read_buf:].tolist()
  l_c.sort()
  #snr_data = np.mean(l_c[-n:])
  snr_data = np.median(l_c)

  print(str(snr_data))

  #take read_buf latest fec readings, select the highest n readings and calculate their average, regardless of antenna
  read_buf = 2
  n = 2
  l_e = e[-n:].tolist()
  #l_e.sort()
  fec_data = np.mean(l_e[-n:])
  print(str(fec_data))

  read_buf = 2
  n = 2
  l_f = f[-n:].tolist()
  #l_e.sort()
  lost_data = np.mean(l_f[-n:])
  print(str(lost_data))





  #Normalize to -1024 -> 1024
  normalize_rssi = normalizeData(rssi_data,-60,-90)
  print("Normalized RSSI: "+str(normalize_rssi))
  normalize_snr = normalizeData(snr_data,20,8)
  print("Normalized SNR: "+str(normalize_snr))
  normalize_fec = -normalizeData(fec_data,35,20)
  print("Normalized FEC: "+str(normalize_fec))
  normalize_lost = -normalizeData(lost_data,35,20)
  print("Normalized Lost: "+str(normalize_lost))



  snr_rssi = (normalize_snr+normalize_rssi)/2
  #combines both SNR and RSSI
  #If more than 8 lost/fec discovered, go to -1024 )

  if (normalize_fec < 0 or normalize_lost < 0) and snr_rssi < 200:
    channel_output = -1024
  else:
    channel_output = snr_rssi
    if channel_output < 0:
        channel_output+25

  #Only RSSI
  #channel_output = normalize_rssi



  #Print what is sent to output
  print("Channel_output: "+ str(channel_output))

  #Set command and execute
  cmd = "/" + str(channel_output) + "/ >> "+args.output
  print("Output "+cmd)
  #Run command

  print("echo output: "+str(subprocess.check_output("echo "+cmd, shell=True)))

  sleep(0.6)
