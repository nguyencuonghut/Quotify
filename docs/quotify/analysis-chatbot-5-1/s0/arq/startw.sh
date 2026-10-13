#!/bin/bash
# usage: startw.sh NAME [VAR=VAL ...]   (module w.WorkerSettings; set SETTINGS=w.Child to override)
S=/tmp/claude-1000/-run-media-cuong-DATA-02-Project-211-Theo-d-i-bi-n---ng-gi--Quotify/87e6330c-b4c9-4188-bd30-54c5b2db3564/scratchpad/s0-arq
N=$1; shift
ENVS=(); SETTINGS=w.WorkerSettings
for kv in "$@"; do case $kv in SETTINGS=*) SETTINGS=${kv#SETTINGS=};; *) ENVS+=(-e "$kv");; esac; done
docker run -d --name s0-arq-$N --network s0-arq-net -v $S:/s0 -e PYTHONPATH=/s0 -e PYTHONDONTWRITEBYTECODE=1 "${ENVS[@]}" -w /s0 --entrypoint arq quotify-backend:latest $SETTINGS >/dev/null
