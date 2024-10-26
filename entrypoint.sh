#!/bin/bash
apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

pip --cache-dir /root/.cache/pip install -r requirements.txt

#bash
python app-multi-source.py