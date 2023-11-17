import sys
from time import time
from typing import Dict
from collections import OrderedDict

from loguru import logger
from sanic import Sanic, json
from sanic.response import text
import socketio
from socketio.exceptions import TimeoutError
import asyncio

from args import parse_args
from utils import append_msg, all_messages_received
from count_down_latch import CountDownLatch

cfg = parse_args()

sio = socketio.AsyncServer(async_mode='sanic', cors_allowed_origins=[])
app = Sanic(f"master_app")

msg_dct = OrderedDict()
msg_idx = 0

latch = CountDownLatch()

@app.get("/")
async def get_lst(_):
    await all_messages_received(msg_dct)
    return json([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in msg_dct.items()])


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
            await latch.coroutine_done()
            await latch.release_if_n_acquired()
        except TimeoutError:
            logger.error(f'Timed out waiting for ACK from slave on port {slave_port}')
        except ValueError:
            logger.error(f"Wrong ACK received from slave on port {slave_port}; recieved - {event}")
        else:
            duration = time() - sent_time
            logger.debug(f'Wrote data {data} to slave ip with port {slave_port}, duration of the coroutine - {duration}')


@app.route("/", methods=['POST'])
async def put_lst(request):
    ts = time()
    concerns = request.json.get("w", None)
    if concerns is None:
        raise ValueError("Number of slave replicas is not provided")
    concerns = int(concerns) - 1

    logger.debug(f'Will be waiting for {concerns} concerns')

    msg = request.json.get("msg", "")
    global msg_idx
    data = {
        "msg": msg,
        "msg_idx": msg_idx,
    }
    append_msg(data, msg_dct)
    msg_idx += 1

    await latch.reset()
    latch.set_n_coroutines(concerns)
    logger.debug(f"Current latch state - {latch.get_latch_state()}")
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
    await latch.wait()

    logger.debug(f'Whole function lasted for {time() - ts}\n')
    return text("200")


def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=int(cfg["master_port"]), debug=True)


if __name__ == "__main__":
    main()