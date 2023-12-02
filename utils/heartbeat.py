import asyncio
from time import time
from typing import Dict

import socketio
from loguru import logger
from socketio.exceptions import ConnectionError

from utils.namespaces import Namespaces


async def permanently_check_heartbeat(
    seconds: int, slave_addr: str, slaves_statuses: Dict[str, str]
):
    while True:
        is_alive = True
        async with socketio.AsyncSimpleClient(request_timeout=1) as sio:
            try:
                await sio.connect(
                    "http://" + slave_addr, namespace=Namespaces.HEART_BEAT
                )
                await sio.emit("is_alive")

                sent_time = time()

                event = await sio.receive()
                if event != ["is_alive"]:
                    raise ValueError
            except ConnectionError:
                logger.error(f"Timed out waiting for ACK from {slave_addr}")
                is_alive = False
            except ValueError:
                logger.error(
                    f"Wrong ACK received from slave {slave_addr}; recieved - {event}"
                )
                is_alive = False
            else:
                duration = time() - sent_time
                logger.debug(
                    f"Recieved alive status from {slave_addr}, duration of the coroutine - {duration}"
                )

        previous_val = slaves_statuses[slave_addr]
        if not is_alive:
            if previous_val == "Healthy":
                new_val = "Suspected"
            elif previous_val == "Suspected":
                new_val = "Unhealthy"
            else:
                new_val = previous_val
        else:
            new_val = "Healthy"

        slaves_statuses[slave_addr] = new_val
        logger.debug(f"For slave {slave_addr}, current status is {new_val}'")

        await asyncio.sleep(seconds)
