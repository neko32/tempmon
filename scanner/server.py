from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import json
from os import getenv
from datetime import datetime
import subprocess

def now_str() -> str:
    dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")

host_name = "0.0.0.0"
server_port = 8031

img_path = getenv("SCANNED_IMG_PATH")
if img_path is None:
    raise RuntimeError("SCANNED_IMG_PATH is not set")


class Server(BaseHTTPRequestHandler):
    def do_GET(self):

        if self.path.startswith("/pict"):
            print(self.path)

            fname = f"{now_str()}.jpeg"
            img_path_obj = f"{img_path}/{fname}"
            try:
                rez = subprocess.run(
                    ["rpicam-jpeg", "-o", str(img_path_obj)],
                    check = True
                )
            except Exception as e:
                raise RuntimeError(e)

            print(f"result code of rpicam-jpeg: {rez.returncode}")

            if rez.returncode != 0:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(bytes("Failed to capture image", "utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(f"{img_path}/{fname}", 'rb') as fp:
                    self.wfile.write(fp.read())



if __name__ == "__main__":

    websrv = HTTPServer((host_name, server_port), Server)
    print(f"starting test server {host_name}:{server_port} .. ")

    try:
        websrv.serve_forever()
    except KeyboardInterrupt:
        pass

    websrv.server_close()
    print("the scanner server stopped.")
