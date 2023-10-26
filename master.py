import sys
from time import time

from loguru import logger
from flask import Flask, jsonify
from flask import request
import socketio
from socketio.exceptions import TimeoutError

from args import parse_args

cfg = parse_args()

app = Flask(__name__)
msg_lst = []



@app.route("/", methods=['GET'])
def get_lst():
    return jsonify([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in enumerate(msg_lst)])

@app.route("/", methods=['POST'])
async def put_lst():
    ts = time()
    concerns = request.get_json().get("w", None)
    if concerns is None:
        raise ValueError("Number of slave replicas is not provided")

    data = request.get_json().get("msg", "")
    msg_lst.append(data)
    accepted_acks = 1
    for slave_ip, slave_port in zip(cfg["slaves_ips"], cfg["slaves_port"]):
        async with socketio.AsyncSimpleClient(logger=True, engineio_logger=True) as sio:
            await sio.connect("http://" + slave_ip + ":" + slave_port)
            await sio.emit('append_msg', data)

            if accepted_acks < concerns:
                sent_time = time()
                try:
                    event = await sio.receive(timeout=cfg["sleep_duration_sec"] + 1)
                    if event != ["appended"]:
                        raise ValueError
                    else:
                        accepted_acks += 1
                except TimeoutError:
                    logger.error(f'Timed out waiting for ACK from slave on port {slave_port}')
                except ValueError:
                    logger.error(f"Wrong ACK received from slave on port {slave_port}")
                else:
                    duration = time() - sent_time
                    logger.debug(f'Wrote data {data} to slave ip with port {slave_port}, duration - {duration}')
            else:
                logger.info(f"Not waiting for concern from slave on port {slave_port}")

    logger.debug(f'Whole function lasted for {time() - ts}')
    return "OK"

def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    app.run(host=cfg["master_ip"], port=cfg["master_port"], debug=True)


if __name__ == "__main__":
    main()