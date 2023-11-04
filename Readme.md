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