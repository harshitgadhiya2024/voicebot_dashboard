FROM ubuntu:20.04

WORKDIR /app

RUN apt-get update && \
    apt-get install -y python3 python3-pip git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 2424

ENV NAME World

CMD ["python3", "main.py"]