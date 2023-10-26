import sys
from threading import Thread

from loguru import logger
# from flask import Flask, jsonify
from sanic import Sanic, json
import socketio
# from flask_socketio import SocketIO

from args import parse_args

cfg = parse_args()

# sio = socketio.Server(async_mode='threading')
sio = socketio.AsyncServer(async_mode='sanic', cors_allowed_origins=[])
# app = socketio.ASGIApp(sio)
app = Sanic(f"slave_{cfg['slave_id']}_app")
sio.attach(app)
# app = Flask(__name__)
# app.wsgi_app = socketio.ASGIApp(sio, app.wsgi_app)
# socketio = SocketIO(app, async_handlers=False)
msg_lst = []


@app.get("/")
async def get_lst(_):
    return json([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in enumerate(msg_lst)])


@sio.on('append_msg')
async def append_msg_handler(sid, data):
    msg_lst.append(data)
    logger.debug(f'Received message {data}')
    await sio.sleep(cfg["sleep_duration_sec"])
    await sio.emit('appended')


def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    try:
        slave_port = cfg["slaves_port"][cfg["slave_id"]]
        slave_ip = cfg["slaves_ips"][cfg["slave_id"]]
    except:
        logger.error(f"No such slave index {cfg['slave_id']}, in {cfg['slaves_ips']}")
        return 1

    # socketio.run(app, host=slave_ip, port=slave_port, debug=True)
    app.run(host=slave_ip, port=int(slave_port), debug=True)



if __name__ == "__main__":
    main()