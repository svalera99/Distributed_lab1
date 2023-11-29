import sys
from time import time
from collections import OrderedDict

from loguru import logger
from sanic import Sanic, json
from sanic.response import text
import socketio
import asyncio

from utils.args import cfg
from utils.utils import (
    append_msg, 
    all_messages_received,
)
from utils.count_down_latch import CountDownLatch
from utils.send import communicate_with_slave

sio = socketio.AsyncServer(async_mode='sanic', cors_allowed_origins=[])
app = Sanic(f"master_app")
sio.attach(app)

msg_dct = OrderedDict()
msg_idx = 0

latch = CountDownLatch()


@app.get("/")
async def get_lst(_):
    await all_messages_received(msg_dct)
    return json([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in msg_dct.items()])


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
    latch.set_parameters(
        n_to_wait_for=concerns,
        n_total=len(cfg["slaves_ips"])
    )
    logger.debug(f"Current latch state - {latch.get_latch_state()}")
    tasks = [
        asyncio.create_task(
            communicate_with_slave(
                slave_ip, 
                slave_port, 
                data,
                latch
            )
        )
        for slave_ip, slave_port in zip(cfg["slaves_ips"], cfg["slaves_port"])
    ]

    if concerns > 0:
        await latch.wait()
    else:
        await asyncio.sleep(2)

    if latch.has_completed_sucessfuly():
        logger.debug((
            f'Whole function lasted for {time() - ts}\n'
            "SUCCESS\n"
        ))
        return text("200")
    else:
        logger.debug((
            f"Writing to slave nodes failed, total {latch.get_failed_tasks()}; "
            f"writes failed {time() - ts}\n"
        ))
        return text("500")


@sio.on('sync_msg')
async def synchronize_slave_msgs(sid: int, slave_msg_dct: OrderedDict):
    logger.debug(f'Received msgs {slave_msg_dct} sid is {sid}; Synchronizing')


    global msg_dct
    common_keys = set(list(slave_msg_dct.keys())).intersection(set(list(msg_dct.keys())))
    logger.debug(f"Updating common keys - {common_keys}")
    for key in common_keys:
        slave_msg_dct[key] = msg_dct[key]

    new_keys = set(list(msg_dct.keys())).difference(list(set(slave_msg_dct.keys())))
    logger.debug(f"Setting new keys common keys - {new_keys}")
    for key in new_keys:
        slave_msg_dct[key] = msg_dct[key]

    await sio.emit('sync_msg', slave_msg_dct)


def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=int(cfg["master_port"]))


if __name__ == "__main__":
    main()