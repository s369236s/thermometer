from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit
import asyncio
from threading import Thread
from bleak import BleakClient
from dataclasses import dataclass
import time
import os

# === 藍牙設定 ===
Mac = "A4:C1:38:BF:0B:36"  # 請替換為你的設備 MAC

@dataclass
class Result:
    temperature: float
    humidity: int
    voltage: float
    battery: int = 0

# === Flask + SocketIO 設定 ===
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, async_mode='threading')  # 重要：使用 threading 模式避免衝突

# 根路徑回傳 index.html
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# 靜態資源路由（可選，Flask 預設支援 /static/...）
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# === 藍牙讀取 + 推送數據的異步任務 ===
async def read_sensor_and_emit():
    print("開始連線到藍牙設備...")
    client = BleakClient(Mac, timeout=30.0)

    try:
        await client.connect()
        print("藍牙連線成功！")

        while True:
            try:
                # 讀取 GATT 特徵值
                buff = await client.read_gatt_char("ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6")

                # 解析數據
                temp = int.from_bytes(buff[0:2], byteorder='little', signed=True) / 100
                humidity = int.from_bytes(buff[2:3], byteorder='little')
                voltage = int.from_bytes(buff[3:5], byteorder='little') / 1000
                battery = round((voltage - 2) / (3 - 2) * 100, 2)

                result = Result(temp, humidity, voltage, int(battery))

                print(result)

                # 使用 SocketIO 推送數據給所有客戶端
                socketio.emit('sensor_data', {
                    'temperature': result.temperature,
                    'humidity': result.humidity,
                    'voltage': result.voltage,
                    'battery': result.battery
                })

            except Exception as e:
                print("讀取錯誤:", e)

            await asyncio.sleep(1)  # 改用 asyncio.sleep 避免阻塞事件循環

    except Exception as e:
        print("藍牙連線失敗:", e)
    finally:
        if client.is_connected:
            await client.disconnect()
            print("藍牙設備已斷開")

# === 在背景執行藍牙任務的函數 ===
def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(read_sensor_and_emit())

# === 啟動伺服器前啟動藍牙任務 ===
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('server_response', {'data': 'Connected to server!'})

if __name__ == '__main__':
    # 建立新事件循環來跑藍牙任務
    loop = asyncio.new_event_loop()
    t = Thread(target=start_background_loop, args=(loop,), daemon=True)
    t.start()

    # 啟動 Flask + SocketIO 伺服器
    socketio.run(app, host='0.0.0.0', port=20088, debug=True, use_reloader=False)