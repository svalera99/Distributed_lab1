import sys
from time import time
from typing import Dict
from collections import OrderedDict

from loguru import logger
from flask import Flask, jsonify
from flask import request
import socketio
from socketio.exceptions import TimeoutError
import asyncio

from args import parse_args
from utils import append_msg

cfg = parse_args()

app = Flask(__name__)
msg_dct = OrderedDict()
msg_idx = 0


@app.route("/", methods=['GET'])
def get_lst():
    return jsonify([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in msg_dct.items()])


async def communicate_with_slave(
    slave_ip: str,
    slave_port: str,
    data: Dict
):
    async with socketio.AsyncSimpleClient() as sio:
        await sio.connect("http://" + slave_ip + ":" + slave_port)
        await sio.emit('append_msg', data)

        sent_time = time()
        try:
            event = await sio.receive()
            if event != ["appended"]:
                raise ValueError
        except TimeoutError:
            logger.error(f'Timed out waiting for ACK from slave on port {slave_port}')
        except ValueError:
            logger.error(f"Wrong ACK received from slave on port {slave_port}; recieved - {event}")
        else:
            duration = time() - sent_time
            logger.debug(f'Wrote data {data} to slave ip with port {slave_port}, duration of the coroutine - {duration}')


@app.route("/", methods=['POST'])
async def put_lst():
    ts = time()
    concerns = request.get_json().get("w", None)
    if concerns is None:
        raise ValueError("Number of slave replicas is not provided")
    concerns = int(concerns) - 1

    msg = request.get_json().get("msg", "")
    global msg_idx
    data = {
        "msg": msg,
        "msg_idx": msg_idx
    }
    append_msg(data, msg_dct)
    msg_idx += 1

    tasks = [
        asyncio.create_task(
            communicate_with_slave(
                slave_ip, 
                slave_port, 
                data
            )
        )
        for slave_ip, slave_port in zip(cfg["slaves_ips"], cfg["slaves_port"])
    ]
    if concerns > 0:
        while True:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks = [task for task in tasks if not task.done()]

            concerns -= len(done)
            if concerns <= 0:
                break
            else:
                logger.debug(f'waiting for {concerns} acks')
    else:
        await asyncio.sleep(2) # wait for tasks coroutines to start

    logger.debug(f'Whole function lasted for {time() - ts}')
    return "OK"


def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=cfg["master_port"], debug=True)


if __name__ == "__main__":
    main()