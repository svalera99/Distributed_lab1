# Steps to reproduce


## Setting up docker
```python
docker build -t slave_master:latest -f docker/Dockerfile .
```

```python
docker network create --subnet=10.5.0.0/16 servers_net
```
## Running master and slaves

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.2  --name master -p 7000:7000 slave_master:latest bash -c "cd /dir && python3 master.py"
```

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.3 --name slave1 -p 8000:8000 --link master slave_master:latest bash -c "cd /dir && python3 slave.py --slave_id 0"
```

```python
docker run --rm -v ${PWD}:/dir --net servers_net --ip 10.5.0.4 --name slave2 -p 9000:9000 --link master slave_master:latest bash -c "cd /dir && python3 slave.py --slave_id 1"
```