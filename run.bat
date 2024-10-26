docker volume create pip_cache
docker volume create apt_cache
docker volume create apt_lists
docker build --build-arg PIP_CACHE_DIR=/root/.cache/pip -t core:latest .
docker run --hostname haccourtechcore --rm -d --network HaccourTech_network --gpus all -v .:/workspace -v apt_cache:/var/cache/apt -v apt_lists:/var/lib/apt/lists  -v pip_cache:/root/.cache/pip --name HaccourTech_Core core:latest