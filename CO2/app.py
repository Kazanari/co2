from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from pyemvue import PyEmVue
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser
import time
import schedule
import webbrowser
import threading
import os
from typing import List, Dict

from pyemvue.device import VueDevice, VueUsageDevice
from pyemvue.enums import Scale, Unit
from pyemvue.pyemvues import PyEmVue

app = Flask(__name__)
CORS(app)  # 允许跨域请求
vue = PyEmVue()

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

# 在文件开头添加全局变量
username = "your_username"
password = "your_password"

def print_recursive(usage_dict: dict[int, VueUsageDevice], info: dict[int, VueDevice], scaleBy: float = 1, unit='kWh', depth=0, interval_type=''):
    instant = datetime.now()
    for gid, device in usage_dict.items():
        for channelnum, channel in device.channels.items():
            usage = channel.usage or 0
            data.append({'type': interval_type, 'time': instant.isoformat(), 'name': channel.name, 'number': usage * scaleBy})
            if channel.nested_devices:
                print_recursive(channel.nested_devices, info, scaleBy=scaleBy, unit=unit, depth=depth+1, interval_type=interval_type)
    return data

def get_data(interval_type):   
    devices = vue.get_devices()
    deviceGids: list[int] = []
    deviceInfo: dict[int, VueDevice] = {}

    for device in devices:
        if not device.device_gid in deviceGids:
            deviceGids.append(device.device_gid)
            deviceInfo[device.device_gid] = device

    now = datetime.now()

    global data
    data = []

    if interval_type == 'second':
        scale = Scale.SECOND.value
        scaleBy=3600000
        unit='W'
    elif interval_type == 'minute':
        scale = Scale.MINUTE.value
        scaleBy=60000
        unit='W'
    elif interval_type == 'hour':
        scale = Scale.HOUR.value
        scaleBy=1
        unit='kWh'
    else:
        scale = Scale.DAY.value
        scaleBy=1
        unit='kWh'

    use = vue.get_device_list_usage(deviceGids, now, scale)
    data = print_recursive(use, deviceInfo, scaleBy, interval_type=interval_type)

    return data

def refresh_data_per_second():
    data = get_data('second')
    with app.app_context():
        response = jsonify(data)
    save_data_to_local(data, 'second')  # 将数据保存到本地
    schedule.every(1).seconds.do(refresh_data_per_second)

def refresh_data_per_minute():
    data = get_data('minute')
    with app.app_context():
        response = jsonify(data)
    save_data_to_local(data, 'minute')  # 将数据保存到本地
    schedule.every(10).seconds.do(refresh_data_per_minute)

def refresh_data_per_hour():
    data = get_data('hour')
    with app.app_context():
        response = jsonify(data)
    save_data_to_local(data, 'hour')  # 将数据保存到本地
    schedule.every(10).minutes.do(refresh_data_per_hour)

def refresh_data_per_day():
    data = get_data('day')
    with app.app_context():
        response = jsonify(data)
    save_data_to_local(data, 'day')  # 将数据保存到本地
    schedule.every(30).minutes.do(refresh_data_per_day)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/data_visualization')
def data_visualization():
    return render_template('data_visualization.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    uname = data['username']
    pword = data['password']

    global vue
    vue = PyEmVue()
    customer = vue.login(uname, pword)

    if customer:
        print("Login successful")  # 添加调试输出

        refresh_data_per_second()  # 程序启动时调用此函数以开始更新数据
        refresh_data_per_minute()  # 程序启动时调用此函数以开始更新数据
        refresh_data_per_hour()  # 程序启动时调用此函数以开始更新数据
        refresh_data_per_day()  # 程序启动时调用此函数以开始更新数据

        return jsonify({"success": True})
    else:
        print("Login failed")  # 添加调试输出
        return jsonify({"success": False}), 401

@app.route('/get_saved_data', methods=['GET'])
def get_saved_data():
    data_types = ['second', 'minute', 'hour', 'day', 'compressed']
    data = {}

    for data_type in data_types:
        file_path = f'static/datas/{data_type}.json'

        try:
            with open(file_path, "r") as file:
                data[data_type] = json.load(file)
        except FileNotFoundError:
            data[data_type] = []
        except json.decoder.JSONDecodeError:
            data[data_type] = []

    return jsonify({'data': data, 'current_time': datetime.now().isoformat()})

@app.route('/update_newname', methods=['POST'])
def update_newname():
    data = request.get_json()
    with open('static/datas/newname.json', 'w') as f:
        json.dump(data, f)
    return jsonify({"result": "success"})

@app.route('/update_matome', methods=['POST'])
def update_matome():
    data = request.get_json()
    with open('static/datas/matome.json', 'w') as f:
        json.dump(data, f)
    return jsonify({"result": "success"})

def save_data_to_local(data_list: List[Dict], data_type: str):
    # 创建文件路径字典
    file_paths = {
        'second': 'static/datas/second.json',
        'minute': 'static/datas/minute.json',
        'hour': 'static/datas/hour.json',
        'day': 'static/datas/day.json',
        'compressed': 'static/datas/compressed.json',
    }

    file_path = file_paths[data_type]

    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 读取已有的数据
    try:
        with open(file_path, "r") as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []
    except json.decoder.JSONDecodeError:
        existing_data = []

    # 如果现有数据是字典，将其转换为列表
    if isinstance(existing_data, dict):
        existing_data = list(existing_data.values())

    # 仅添加与当前类型匹配的数据
    new_data = [d for d in data_list if d['type'] == data_type]

    compressed_data = []

    for new_item in new_data:
        new_item_time = datetime.fromisoformat(new_item['time'])
        found = False

        for i, existing_item in enumerate(existing_data):
            existing_item_time = datetime.fromisoformat(existing_item['time'])

            if existing_item['type'] == new_item['type'] and existing_item['name'] == new_item['name']:
                if data_type == 'second':
                    new_item_time = new_item_time.replace(microsecond=0)
                    existing_item_time = existing_item_time.replace(microsecond=0)
                elif data_type == 'minute':
                    new_item_time = new_item_time.replace(second=0, microsecond=0)
                    existing_item_time = existing_item_time.replace(second=0, microsecond=0)
                elif data_type == 'hour':
                    new_item_time = new_item_time.replace(minute=0, second=0, microsecond=0)
                    existing_item_time = existing_item_time.replace(minute=0, second=0, microsecond=0)
                elif data_type == 'day':
                    new_item_time = new_item_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    existing_item_time = existing_item_time.replace(hour=0, minute=0, second=0, microsecond=0)

                if new_item_time == existing_item_time:
                    found = True
                    existing_data[i] = new_item
                    break

        if not found:
            existing_data.append(new_item)

    # 根据数据类型截断数据
    if data_type == 'second':
        cutoff_time = datetime.now() - timedelta(minutes=10)
    elif data_type == 'minute':
        cutoff_time = datetime.now() - timedelta(hours=1)
    elif data_type  == 'hour':
        cutoff_time = datetime.now() - timedelta(days=1)
    elif data_type == 'day':
        cutoff_time = datetime.now() - timedelta(days=30)
    else:
        cutoff_time = datetime.now() - timedelta(days=365)

    compressed_data = [d for d in existing_data if (isinstance(d['time'], str) and datetime.fromisoformat(d['time'])< cutoff_time)]
    existing_data = [d for d in existing_data if (isinstance(d['time'], str) and datetime.fromisoformat(d['time']) >= cutoff_time)]

    # 将更新后的数据保存到文件
    with open(file_path, 'w') as file:
        json.dump(existing_data, file, cls=DateTimeEncoder)

    # 将超时数据保存到compressed文件
    compressed_file_path = file_paths['compressed']

    # 读取已有的压缩数据
    try:
        with open(compressed_file_path, "r") as file:
            existing_compressed_data = json.load(file)
    except FileNotFoundError:
        existing_compressed_data = []
    except json.decoder.JSONDecodeError:
        existing_compressed_data = []

    # 添加新的超时数据
    existing_compressed_data.extend(compressed_data)

    # 将更新后的压缩数据保存到文件
    with open(compressed_file_path, 'w') as file:
        json.dump(existing_compressed_data, file, cls=DateTimeEncoder)

if __name__ == '__main__':
    url = 'http://localhost:12345/login'
    webbrowser.open_new_tab(url)

    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()

    app.run(port=12345)


