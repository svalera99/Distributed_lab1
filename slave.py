import sys
from collections import OrderedDict
from time import sleep, time

import numpy as np
import socketio
from loguru import logger
from sanic import Sanic, json
from socketio.exceptions import ConnectionError

from utils.args import cfg
from utils.namespaces import Namespaces
from utils.utils import all_messages_received, append_msg

sio = socketio.AsyncServer(async_mode="sanic", cors_allowed_origins=[])
app = Sanic(f"slave_{cfg['slave_id']}_app")
sio.attach(app)
msg_dct = OrderedDict()


@app.get("/")
async def get_lst(_):
    await all_messages_received(msg_dct)
    return json(
        [
            f"Message number - {msg_inx}, message - {msg}"
            for msg_inx, msg in msg_dct.items()
        ]
    )


async def emulate_transmition_failure():
    looping_kind = cfg["delivery_failure"]["kind"]
    if (
        looping_kind == "server_unavailable"
        and cfg["delivery_failure"]["servers_dead"][cfg["slave_id"]]
    ):
        app.stop()
    elif looping_kind == "internal_loping":
        await sio.sleep(cfg["delivery_failure"][cfg["slave_id"]])


@sio.on("is_alive", namespace=Namespaces.HEART_BEAT)
async def server_is_alive(sid, data=None):
    await sio.emit("is_alive", namespace=Namespaces.HEART_BEAT)


@sio.on("append_msg", namespace=Namespaces.SEND)
async def append_msg_handler(sid, data):
    logger.debug(f"Received message {data} sid is {sid}")

    await emulate_transmition_failure()

    wait_time = cfg["sleep_duration_sec"] + np.random.randint(-4, 4)
    logger.debug(f"Waiting for {wait_time}")
    await sio.sleep(wait_time)

    append_msg(data, msg_dct)

    logger.debug(f"Appended message {data['msg']} with index {data['msg_idx']}")
    await sio.emit("appended", namespace=Namespaces.SEND)


@app.listener("before_server_start")
def synchronize(app, loop):
    global msg_dct
    while True:
        logger.debug("Starting sync process")
        with socketio.SimpleClient() as sio:
            try:
                sio.connect(
                    "http://" + cfg["master_ip"] + ":" + cfg["master_port"],
                    namespace=Namespaces.SYNC,
                )
                sio.emit("sync_msg", msg_dct)

                sent_time = time()

                msg_name, updated_msg_dct = sio.receive()
                if msg_name != "sync_msg":
                    raise ValueError
                if type(updated_msg_dct) != dict:
                    logger.error(
                        f"Something wrong received; actuall type - {type(updated_msg_dct)};"
                        f"actual value - {updated_msg_dct}"
                    )

                logger.debug(f"Received new msgs - {updated_msg_dct}")
                msg_dct = OrderedDict()
                for key, val in updated_msg_dct.items():
                    msg_dct[int(key)] = val
            except ConnectionError:
                logger.error(
                    "Master hasn't responded  with an updated;"
                    f"master ip - {cfg['master_ip']}"
                )
                sleep(5)
            except ValueError:
                logger.error(
                    f"Wrong message received, expected sync_msg; Got - {msg_name}"
                )
                sleep(5)
            else:
                duration = time() - sent_time
                logger.debug(
                    f"Updated msgs after reconnecting {duration};"
                    f"New value of msgs - {msg_dct}"
                )
                break


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
