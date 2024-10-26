FROM core:base

# Crie um volume para o cache do apt
VOLUME /var/cache/apt
VOLUME  /var/lib/apt/lists 
# Crie um volume para o cache do pip
VOLUME /root/.cache/pip

COPY ./*.py /workspace
COPY ./*.pyc /workspace
COPY ./*.pt /workspace
COPY ./*.md /workspace
COPY ./*.dat /workspace
COPY ./requirements.txt /workspace
COPY ./entrypoint.sh /workspace

RUN chmod +x /workspace/entrypoint.sh

WORKDIR /workspace

ENTRYPOINT [ "/workspace/entrypoint.sh" ]