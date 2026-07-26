#!/usr/bin/python3
import socket
import struct
import sys

#Example using socat:
#(echo -n -e '\x00\x00\x00\x31'; echo -n 'special:run_command:/etc/init.d/S95majestic start') | socat - UDP-DATAGRAM:192.168.1.53:9999

#Example using this program:
#adaptive_link_send_command.py '/etc/init.d/S95majestic start'

def send_udp_command(command, ip, port):
    # Format the command with "special:run_command:<command>"
    message = f"special:run_command:{command}"
    
    # Calculate the length of the message (in bytes)
    message_length = len(message)
    
    # Create the 4-byte size prefix in network byte order (big-endian)
    size_prefix = struct.pack('!I', message_length)
    
    # Combine the size prefix and the message
    udp_packet = size_prefix + message.encode('utf-8')
    
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Send the packet to the specified IP and port
    sock.sendto(udp_packet, (ip, port))
    
    # Close the socket
    sock.close()

# Example usage:
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 script.py '<command>'")
        sys.exit(1)
    
    # Take the first argument as the command
    command = sys.argv[1]
    
    # Define the target IP and port (these can be modified as needed)
    target_ip = "127.0.0.1"  # Target IP
    target_port = 9999       # Target Port
    
    send_udp_command(command, target_ip, target_port)
