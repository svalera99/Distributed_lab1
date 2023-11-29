import sys
from time import time
from typing import Dict
from collections import OrderedDict

from loguru import logger
from sanic import Sanic, json
from sanic.response import text
import socketio
from socketio.exceptions import TimeoutError, ConnectionError
import asyncio
from asyncio.exceptions import TimeoutError as ASYNC_TimeoutError

from args import cfg
from utils import (
    append_msg, 
    all_messages_received,
    get_ith_timeout
)
from count_down_latch import CountDownLatch

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
    wait_inx = 0
    starting_time = time()

    while timeout_condition := (time() - starting_time) < cfg["connection_timeout"]:
        try:
            await asyncio.wait_for(
                send_msg(slave_ip, slave_port, data),
                timeout=cfg["connection_timeout"]
            )
            return 0
        except ConnectionError:
            next_waiting_time = get_ith_timeout(wait_inx)
            wait_inx += 1
            if timeout_condition := (time() - starting_time) < cfg["connection_timeout"]:
                logger.error((
                    f"Couldn't connect to slave {slave_ip}:{slave_port};"
                    f"Retrying in {next_waiting_time}"
                ))
                await asyncio.sleep(next_waiting_time)
                continue
        except ASYNC_TimeoutError:
            logger.error((
                f"Connection to {slave_ip}:{slave_port} was established;"
                f"But no results was recieved in {cfg['connection_timeout']} seconds"
            ))

    logger.error(f"Couldn't connect to slave {slave_ip}:{slave_port}; Abort")
    await latch.add_failed_task()
    await latch.release_if_m_failed()


async def send_msg(
    slave_ip: str,
    slave_port: str,
    data: Dict
):
    async with socketio.AsyncSimpleClient(request_timeout=1) as sio:
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


async def delete_msg_from_slave(
    slave_ip: str,
    slave_port: str,
    data: Dict
):

    async with socketio.AsyncSimpleClient(request_timeout=1) as sio:
        await sio.connect("http://" + slave_ip + ":" + slave_port)
        await sio.emit('delete_msg', data)

        sent_time = time()
        try:
            event = await sio.receive()
            if event != ["deleted"]:
                raise ValueError
            await latch.coroutine_done()
            await latch.release_if_n_acquired()
        except TimeoutError:
            logger.error(f'Timed out waiting for delete ACK from slave on port {slave_port}')
        except ValueError:
            logger.error(f"Wrong delete ACK received from slave on port {slave_port}; recieved - {event}")
        else:
            duration = time() - sent_time
            logger.debug(f'Deleted data {data} from slave ip with port {slave_port}, duration of the coroutine - {duration}')



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
                data
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



def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=int(cfg["master_port"]), debug=True)


if __name__ == "__main__":
    main()