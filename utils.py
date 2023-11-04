from typing import Dict
from collections import OrderedDict


def append_msg(data: Dict, msg_dct: OrderedDict):
    msg_inx = data["msg_idx"]
    msg = data["msg"]
    if msg_inx not in msg_dct:
        msg_dct[msg_inx] = msg
        msg_dct = sorted(msg_dct.items())