import socket
import sys

def check_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        result = s.connect_ex(('127.0.0.1', 5000))
        if result == 0:
            print("Port 5000 is OPEN")
        else:
            print(f"Port 5000 is CLOSED (code: {result})")
    except Exception as e:
        print(f"Error checking port: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    check_port()
