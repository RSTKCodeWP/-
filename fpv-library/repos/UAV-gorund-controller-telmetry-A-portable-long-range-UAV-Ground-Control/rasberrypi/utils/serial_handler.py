import serial from config import ( SERIAL_PORT, BAUD_RATE )
ser = serial.Serial( SERIAL_PORT, BAUD_RATE, timeout=1 ) 
def send_data(data): 
    ser.write( data.encode() )
    
def receive_data(): 
    if ser.in_waiting: 
        return ser.readline().decode() 
    return None