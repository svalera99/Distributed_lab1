import argparse
from yaml import safe_load


def parse_args():
    parser = argparse.ArgumentParser(description="Provide path to the config")
    parser.add_argument("--config_p", '-p', default="config.yaml")
    parser.add_argument("--slave_id", '-s', required=False, default=0, type=int)

    cfg = vars(parser.parse_args())
    with open(cfg["config_p"]) as file:
        cfg_content = safe_load(file)

    cfg_content["slave_id"] = cfg["slave_id"]
    return cfg_content

cfg = parse_args()