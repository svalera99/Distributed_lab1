import asyncio
import sys
from collections import OrderedDict
from math import floor
from time import time

import socketio
from loguru import logger
from sanic import Sanic, json
from sanic.response import text

from utils.args import cfg
from utils.count_down_latch import CountDownLatch
from utils.heartbeat import permanently_check_heartbeat
from utils.namespaces import Namespaces
from utils.send import communicate_with_slave
from utils.utils import all_messages_received, append_msg

sio = socketio.AsyncServer(async_mode="sanic", cors_allowed_origins=[])
app = Sanic(f"master_app")
sio.attach(app)

msg_dct = OrderedDict()
msg_idx = 0

slaves_statuses = {
    ip + ":" + port: "Healthy"
    for ip, port in zip(cfg["slaves_ips"], cfg["slaves_port"])
}


@app.get("/")
async def get_lst(_):
    await all_messages_received(msg_dct)
    return json(
        [
            f"Message number - {msg_inx}, message - {msg}"
            for msg_inx, msg in msg_dct.items()
        ]
    )


async def prerequisites_met(concerns: int):
    global slaves_statuses
    dead_slaves = len(
        [
            slave_addr
            for slave_addr, slave_status in slaves_statuses.items()
            if slave_status == "Unhealthy"
        ]
    )
    alive_slaves = len(
        [
            slave_addr
            for slave_addr, slave_status in slaves_statuses.items()
            if slave_status in ["Healthy", "Suspected"]
        ]
    )

    quorum_number = int(floor((1 + len(cfg["slaves_ips"])) / 2))
    if cfg["enforce_quorum"] and alive_slaves + 1 < quorum_number:
        logger.debug(
            (
                f"Alive servers - {alive_slaves}, required for quorum - {quorum_number}"
                f"Not Enough slaves are alive to reach quorum; Aborting"
                "FAILURE\n"
            )
        )
        return False

    if cfg["suspend_on_slaves_dead"] and alive_slaves < concerns:
        logger.debug(
            (
                f"Dead slaves {dead_slaves}, concerns - {concerns}"
                f"Not Enough slaves are alive in order to fulfil concerns requirement "
                "FAILURE\n"
            )
        )
        return False

    return True


@app.route("/", methods=["POST"])
async def put_lst(request):
    concerns = request.json.get("w", None)
    if concerns is None:
        raise ValueError("Number of slave replicas is not provided")
    concerns = int(concerns) - 1

    assert await prerequisites_met(concerns), "Finishing POST method"

    latch = CountDownLatch()
    ts = time()

    logger.debug(f"Will be waiting for {concerns} concerns")
    msg = request.json.get("msg", "")
    global msg_idx
    data = {
        "msg": msg,
        "msg_idx": msg_idx,
    }
    append_msg(data, msg_dct)
    msg_idx += 1

    await latch.reset()
    latch.set_parameters(n_to_wait_for=concerns, n_total=len(cfg["slaves_ips"]))
    logger.debug(f"Current latch state - {latch.get_latch_state()}")
    tasks = [
        asyncio.create_task(communicate_with_slave(slave_ip, slave_port, data, latch))
        for slave_ip, slave_port in zip(cfg["slaves_ips"], cfg["slaves_port"])
    ]

    if concerns > 0:
        await latch.wait()
    else:
        await asyncio.sleep(2)

    if latch.has_completed_sucessfuly():
        logger.debug((f"Whole function lasted for {time() - ts}\n" "SUCCESS\n"))
        return text("200")
    else:
        logger.debug(
            (
                f"Writing to slave nodes failed, total {latch.get_failed_tasks()}; "
                f"writes failed {time() - ts}\n"
            )
        )
        return text("500")


@sio.on("sync_msg", namespace=Namespaces.SYNC)
async def synchronize_slave_msgs(sid: int, slave_msg_dct: OrderedDict):
    logger.debug(f"Received msgs {slave_msg_dct} sid is {sid}; Synchronizing")

    global msg_dct
    common_keys = set(list(slave_msg_dct.keys())).intersection(
        set(list(msg_dct.keys()))
    )
    logger.debug(f"Updating common keys - {common_keys}")
    for key in common_keys:
        slave_msg_dct[key] = msg_dct[key]

    new_keys = set(list(msg_dct.keys())).difference(list(set(slave_msg_dct.keys())))
    logger.debug(f"Setting new keys common keys - {new_keys}")
    for key in new_keys:
        slave_msg_dct[key] = msg_dct[key]

    await sio.emit("sync_msg", slave_msg_dct, namespace=Namespaces.SYNC)


@app.listener("before_server_start")
async def setup_background_task(app, loop):
    global slaves_statuses
    for slave_addr in slaves_statuses.keys():
        app.add_task(
            permanently_check_heartbeat(
                seconds=cfg["heartbeat_seconds"],
                slave_addr=slave_addr,
                slaves_statuses=slaves_statuses,
            )
        )


async def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=int(cfg["master_port"]))


if __name__ == "__main__":
    asyncio.run(main())
