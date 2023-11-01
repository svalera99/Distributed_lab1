import sys
from threading import Thread

from loguru import logger
import numpy as np
from sanic import Sanic, json
import socketio

from args import parse_args

cfg = parse_args()

sio = socketio.AsyncServer(async_mode='sanic', cors_allowed_origins=[])
app = Sanic(f"slave_{cfg['slave_id']}_app")
sio.attach(app)
msg_lst = []


@app.get("/")
async def get_lst(_):
    return json([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in enumerate(msg_lst)])


@sio.on('append_msg')
async def append_msg_handler(sid, data):
    logger.debug(f'Received message {data} sid is {sid}')

    wait_time = cfg["sleep_duration_sec"] + np.random.choice([-1, 1])
    logger.debug(f'Waiting for {wait_time}')
    await sio.sleep(wait_time)

    msg_lst.append(data)
    logger.debug(f"Appended message {data}")
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

    app.run(host=slave_ip, port=int(slave_port))



if __name__ == "__main__":
    main()