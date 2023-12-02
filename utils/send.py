import asyncio
from asyncio.exceptions import TimeoutError as ASYNC_TimeoutError
from time import time
from typing import Dict

import socketio
from loguru import logger
from socketio.exceptions import ConnectionError, TimeoutError

from utils.args import cfg
from utils.count_down_latch import CountDownLatch
from utils.namespaces import Namespaces
from utils.utils import get_ith_timeout


async def communicate_with_slave(
    slave_ip: str, slave_port: str, data: Dict, latch: CountDownLatch
):
    wait_inx = 0
    starting_time = time()

    while timeout_condition := (time() - starting_time) < cfg["connection_timeout"]:
        try:
            await asyncio.wait_for(
                send_msg(slave_ip, slave_port, data, latch),
                timeout=cfg["connection_timeout"],
            )
            return 0
        except ConnectionError:
            next_waiting_time = get_ith_timeout(wait_inx)
            wait_inx += 1
            if (
                timeout_condition := (time() - starting_time)
                < cfg["connection_timeout"]
            ):
                logger.error(
                    (
                        f"Couldn't connect to slave {slave_ip}:{slave_port};"
                        f"Retrying in {next_waiting_time}"
                    )
                )
                await asyncio.sleep(next_waiting_time)
                continue
        except ASYNC_TimeoutError:
            logger.error(
                (
                    f"Connection to {slave_ip}:{slave_port} was established;"
                    f"But no results was recieved in {cfg['connection_timeout']} seconds"
                )
            )

    logger.error(f"Couldn't connect to slave {slave_ip}:{slave_port}; Abort")
    await latch.add_failed_task()
    await latch.release_if_m_failed()


async def send_msg(slave_ip: str, slave_port: str, data: Dict, latch: CountDownLatch):
    async with socketio.AsyncSimpleClient(request_timeout=1) as sio:
        await sio.connect(
            "http://" + slave_ip + ":" + slave_port, namespace=Namespaces.SEND
        )
        await sio.emit("append_msg", data)

        sent_time = time()
        try:
            event = await sio.receive()
            if event != ["appended"]:
                raise ValueError
            await latch.coroutine_done()
            await latch.release_if_n_acquired()
        except TimeoutError:
            logger.error(f"Timed out waiting for ACK from slave on port {slave_port}")
        except ValueError:
            logger.error(
                f"Wrong ACK received from slave on port {slave_port}; recieved - {event}"
            )
        else:
            duration = time() - sent_time
            logger.debug(
                f"Wrote data {data} to slave ip with port {slave_port}, duration of the coroutine - {duration}"
            )
