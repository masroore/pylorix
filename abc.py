import ioloop
import iostream
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
s.connect(("friendfeed.com", 80))
stream = IOStream(s)

def on_headers(data):
    headers = {}
    for line in data.split("\r\n"):
       parts = line.split(":")
       if len(parts) == 2:
           headers[parts[0].strip()] = parts[1].strip()
    stream.read_bytes(int(headers["Content-Length"]), on_body)

def on_body(data):
    print data
    stream.close()
    ioloop.IOLoop.instance().stop()

stream.write("GET / HTTP/1.0\r\n\r\n")
stream.read_until("\r\n\r\n", on_headers)
ioloop.IOLoop.instance().start()
