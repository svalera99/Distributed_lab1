import sys
from collections import OrderedDict

from loguru import logger
import numpy as np
from sanic import Sanic, json
import socketio

from args import cfg
from utils import append_msg, all_messages_received

sio = socketio.AsyncServer(async_mode='sanic', cors_allowed_origins=[])
app = Sanic(f"slave_{cfg['slave_id']}_app")
sio.attach(app)
msg_dct = OrderedDict()


@app.get("/")
async def get_lst(_):
    await all_messages_received(msg_dct)
    return json([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in msg_dct.items()])


async def emulate_transmition_failure():
    looping_kind = cfg["delivery_failure"]["kind"]
    if looping_kind == "server_unavailable" and \
        cfg["delivery_failure"]["servers_dead"][cfg["slave_id"]]:

        app.stop()
    elif looping_kind == "internal_loping":
        await sio.sleep(cfg["delivery_failure"][cfg["slave_id"]])


@sio.on('append_msg')
async def append_msg_handler(sid, data):
    logger.debug(f'Received message {data} sid is {sid}')

    await emulate_transmition_failure()

    wait_time = cfg["sleep_duration_sec"] + np.random.randint(-4, 4)
    logger.debug(f'Waiting for {wait_time}')
    await sio.sleep(wait_time)

    append_msg(data, msg_dct)

    logger.debug(f"Appended message {data['msg']} with index {data['msg_idx']}")
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