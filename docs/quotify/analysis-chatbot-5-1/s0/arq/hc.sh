#!/bin/bash
S=/tmp/claude-1000/-run-media-cuong-DATA-02-Project-211-Theo-d-i-bi-n---ng-gi--Quotify/87e6330c-b4c9-4188-bd30-54c5b2db3564/scratchpad/s0-arq
cd $S
chk() { local env="$1"; docker exec -w /s0 -e PYTHONPATH=/s0 $env s0-arq-client arq --check w.WorkerSettings >/tmp/chk.out 2>&1; echo "   exit=$? $(date +%T) :: $(tail -c 100 /tmp/chk.out | tr -d '\n')"; }
docker rm -f s0-arq-w8 >/dev/null 2>&1; docker exec s0-arq-redis redis-cli flushall >/dev/null
./startw.sh w8 QUEUE=quotify:bot HC_INTERVAL=5 KEEP_RESULT=0 MAX_TRIES=1; sleep 1.5
# bounded wait for a fresh refresh (pttl > 5500)
for i in $(seq 1 120); do P=$(docker exec s0-arq-redis redis-cli --raw pttl quotify:bot:health-check); [ "$P" -gt 5500 ] 2>/dev/null && break; sleep 0.05; done
docker kill -s KILL s0-arq-w8 >/dev/null; echo "SIGKILL at $(date +%T.%N | cut -c1-12) (key pttl was $P ms; interval=5s -> TTL 6s)"
sleep 0.3; chk "-e QUEUE=quotify:bot -e HC_INTERVAL=5"; sleep 2; chk "-e QUEUE=quotify:bot -e HC_INTERVAL=5"; sleep 4; chk "-e QUEUE=quotify:bot -e HC_INTERVAL=5"
docker rm -f s0-arq-w8 >/dev/null
echo "#### default HC_INTERVAL=3600: key TTL & flush scenario"
./startw.sh w8 QUEUE=quotify:bot KEEP_RESULT=0 MAX_TRIES=1; sleep 2
echo "pttl of health key with default interval: $(docker exec s0-arq-redis redis-cli --raw pttl quotify:bot:health-check) ms"
chk "-e QUEUE=quotify:bot"
docker exec s0-arq-redis redis-cli flushall >/dev/null; echo "(simulated Redis restart w/o persistence: FLUSHALL) worker still alive: $(docker inspect -f '{{.State.Running}}' s0-arq-w8)"; sleep 3; chk "-e QUEUE=quotify:bot"
docker kill -s KILL s0-arq-w8 >/dev/null; docker rm -f s0-arq-w8 >/dev/null
echo "#### default interval: alive then SIGKILL (key lives 1h)"
./startw.sh w8 QUEUE=quotify:bot KEEP_RESULT=0 MAX_TRIES=1; sleep 2; docker kill -s KILL s0-arq-w8 >/dev/null; sleep 5; chk "-e QUEUE=quotify:bot"; echo "pttl after SIGKILL: $(docker exec s0-arq-redis redis-cli --raw pttl quotify:bot:health-check) ms"
docker rm -f s0-arq-w8 >/dev/null
