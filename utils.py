from typing import Dict
from collections import OrderedDict

from loguru import logger
import asyncio


def append_msg(data: Dict, msg_dct: OrderedDict):
    msg_inx = data["msg_idx"]
    msg = data["msg"]
    if msg_inx not in msg_dct:
        msg_dct[msg_inx] = msg
        msg_dct = sorted(msg_dct.items())


async def all_messages_received(msg_dct: OrderedDict):
    msg_indexes = list(msg_dct.keys())
    if msg_indexes:
        messaged_received = (msg_indexes == list(range(msg_indexes[0], msg_indexes[-1]+1)))
    else:
        messaged_received = True

    if messaged_received:
        logger.debug(f"All messages up to index {len(msg_indexes)} were received")
        return True
    else:
        logger.debug(f"Still waiting for some messages to arrive till index {len(msg_indexes)}")
        return False