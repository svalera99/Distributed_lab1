import sys

from loguru import logger
from flask import Flask, jsonify
from flask_socketio import SocketIO

from args import parse_args

cfg = parse_args()

app = Flask(__name__)
socketio = SocketIO(app, async_handlers=True)
msg_lst = []


@app.route("/", methods=['GET'])
def get_lst():
    return jsonify([f"Message number - {msg_inx}, message - {msg}" for msg_inx, msg in enumerate(msg_lst)])


@socketio.on('append_msg')
def append_msg(data):
    msg_lst.append(data)
    logger.debug(f'Received message {data}')
    socketio.sleep(cfg["sleep_duration_sec"])
    socketio.emit('appended')


def main():
    logger.remove()
    logger.add(sys.stdout, level=cfg["log_level"])
    logger.add("logs.log", level=cfg["log_level"], backtrace=True, diagnose=True)

    try:
        slave_port = cfg["slaves_port"][cfg["slave_id"]]
        slave_ip = cfg["slaves_ips"][cfg["slave_id"]]
    except:
        logger.error(f"No such slave index {cfg['slave_id']}, in {cfg['slaves_ips']}")
        return 1

    socketio.run(app, host=slave_ip, port=slave_port, debug=True)


if __name__ == "__main__":
    main()