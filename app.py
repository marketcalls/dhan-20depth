from flask import Flask, render_template, jsonify
import websockets
import asyncio
import json
import struct
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Flask app setup
app = Flask(__name__)
app.debug = os.getenv('DEBUG_MODE', 'False').lower() in ('true', '1', 't')

class DhanDepthWebSocket:
    def __init__(self):
        self.token = os.getenv('DHAN_TOKEN', 'eyxxxxx')
        self.client_id = os.getenv('DHAN_CLIENT_ID', '100xxxxxxx')
        self.ws_url = f"wss://depth-api-feed.dhan.co/twentydepth?token={self.token}&clientId={self.client_id}&authType=2"
        self.depth_data = {"bids": [], "offers": []}

    def log(self, message):
        """Ensure immediate logging output"""
        print(message, flush=True)

    async def connect(self):
        async with websockets.connect(self.ws_url) as websocket:
            self.log("WebSocket connected successfully")
            # Subscribe to instruments
            subscribe_message = {
                "RequestCode": 23,
                "InstrumentCount": 1,
                "InstrumentList": [
                    {
                        "ExchangeSegment": "NSE_EQ",
                        "SecurityId": "2885"  # Replace with your security ID
                    }
                ]
            }
            await websocket.send(json.dumps(subscribe_message))
            
            while True:
                try:
                    message = await websocket.recv()
                    await self.process_binary_message(message)
                except websockets.exceptions.ConnectionClosed:
                    self.log("Connection closed. Reconnecting...")
                    break
                except Exception as e:
                    self.log(f"Error: {e}")
                    break

    async def process_binary_message(self, message):
        # Parse header (first 12 bytes)
        if len(message) < 12:
            self.log("Error: Message too short - Please subscribe to Data APIs")
            return

        header = message[:12]
        msg_length, feed_code, exchange_segment, security_id, _ = struct.unpack('!h2bi4s', header)

        if feed_code in [41, 51]:  # 41 for Bid, 51 for Ask
            depth_data = []
            # Process 20 packets of 16 bytes each
            for i in range(20):
                start = 12 + (i * 16)
                end = start + 16
                packet = message[start:end]
                price, quantity, orders = struct.unpack('!dII', packet)
                depth_data.append({
                    "price": price,
                    "quantity": quantity,
                    "orders": orders
                })

            if feed_code == 41:
                self.depth_data["bids"] = depth_data
            elif feed_code == 51:
                self.depth_data["offers"] = depth_data

depth_socket = DhanDepthWebSocket()

@app.route('/config')
def get_config():
    """Endpoint to securely provide credentials to frontend"""
    return jsonify({
        'token': os.getenv('DHAN_TOKEN', ''),
        'clientId': os.getenv('DHAN_CLIENT_ID', '')
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_market_depth')
def get_market_depth():
    return jsonify(depth_socket.depth_data)

def start_websocket():
    while True:
        try:
            asyncio.run(depth_socket.connect())
        except Exception as e:
            print(f"Connection error: {e}", flush=True)
        time.sleep(5)

if __name__ == '__main__':
    import threading
    ws_thread = threading.Thread(target=start_websocket)
    ws_thread.daemon = True
    ws_thread.start()
    app.run(debug=app.debug, use_reloader=False)
