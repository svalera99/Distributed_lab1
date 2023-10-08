FROM ubuntu:22.04

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git && \
    apt-get install -y python3 python3-pip &&\
    rm -rf /var/lib/apt/lists/*

RUN mkdir /req_dir
COPY requirements.txt /req_dir
RUN pip install -r /req_dir/requirements.txt

RUN git clone https://github.com/miguelgrinberg/python-socketio
RUN pip install python-socketio/.
RUN rm -rf python-socketio

CMD ["/bash/bash"]