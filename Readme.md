# Updates for lab3

1. When slave server starts it automatically resynchronizes with master.
In configs there is "delivery_failure" configs, if should either
automatically turn off slave of make it sleep for a while.

2. Retries are implemeneted with sockets in func send/communicate_with_slave
They are unlimited and retries happend with delay as power of two.
Timeout - "connection_timeout"

3. Deduplication and total order is reached by simply storing index.

4. Heartbeats are implemented with sockets. I create a background
task for sanic server and it sends hearbeats to slaves every "heartbeat_seconds".
Config parameter "suspend_on_slaves_dead" makes that master don't attempt to
send msg to slaves if the nunber of concerns is more than alive slaves.

5. Quorum is controlled by "suspend_on_slaves_dead". In case of one master and
two slaves, if both slaves are dead then post requests will be turned off.



# Steps to reproduce

You can use my lab with running master, slave1, slave2 in separate
consoles to see logs more clear, or using docker compose.

## Building docker images
```python
docker build -t slave_master:latest -f docker/Dockerfile .
```

## Old ways to run

#### Creating network
```python
docker network create --subnet=10.5.0.0/16 servers_net
```
#### Running master and slaves

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.2  --name master -p 7000:7000 slave_master:latest bash -c "cd /dir && python3 master.py"
```

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.3 --name slave1 -p 8000:8000 --link master slave_master:latest bash -c "cd /dir && python3 slave.py --slave_id 0"
```

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.4 --name slave2 -p 9000:9000 --link master slave_master:latest bash -c "cd /dir && python3 slave.py --slave_id 1"
```

## New way
```cmd
docker compose up
```



## Queries 
POST
```bash
curl -X POST 10.5.0.2:7000 -d '{"msg": "kek", "w": 3}' -H "Content-Type: application/json"
```
GET
```bash
curl 10.5.0.2:7000
curl 10.5.0.3:8000
curl 10.5.0.4:9000
```

# Description of my work

To make everything work async I've configured proper async
message transmition with python asyncio. I've fullfiled the 'concerns'
functionality by not awaiting the tasks when the number of concerns
has already reached the desired level.    
I use simple increasing index to ensure message total ordering and use
that same index to not append messages if they are duplicated.  
I've decided to migrate from flask to Sanic on slave servers
because it gives better debug options and overall pretier.



