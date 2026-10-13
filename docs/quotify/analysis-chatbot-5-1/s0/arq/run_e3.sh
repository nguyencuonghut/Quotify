#!/bin/bash
# usage: run_e3.sh KEEP_RESULT NEW_WORKER_DELAY(s or "none") DUR [extra-probe(yes/no)]
S=/tmp/claude-1000/-run-media-cuong-DATA-02-Project-211-Theo-d-i-bi-n---ng-gi--Quotify/87e6330c-b4c9-4188-bd30-54c5b2db3564/scratchpad/s0-arq
KR=$1; DELAY=$2; DUR=$3
cd $S
docker rm -f s0-arq-w3 s0-arq-w3b >/dev/null 2>&1; docker exec s0-arq-redis redis-cli flushall >/dev/null
./startw.sh w3 JOB_TIMEOUT=6 MAX_TRIES=1 KEEP_RESULT=$KR; sleep 1.2
docker exec -e DUR=$DUR -w /s0 s0-arq-client python e3.py > e3.out 2>&1 &
CP=$!
until grep -q RUNNING e3.out; do sleep 0.1; done
sleep 2
KT=$(date +%s.%N); docker kill -s KILL s0-arq-w3 >/dev/null; echo "$KT HOST SIGKILL worker (job started ~2s earlier)" | tee -a e3.out
if [ "$DELAY" != "none" ]; then
  sleep $DELAY
  ST=$(date +%s.%N); ./startw.sh w3b JOB_TIMEOUT=6 MAX_TRIES=1 KEEP_RESULT=$KR; echo "$ST HOST started new worker w3b" | tee -a e3.out
  if [ "$4" = "yes" ]; then sleep 2; docker exec -w /s0 s0-arq-client python -c "
import asyncio
from client import *
async def m():
    p=await pool(); j=await p.enqueue_job('quick','different-id',_job_id='bot:8'); log('HOST-probe different id bot:8 enqueue ->', j); await asyncio.sleep(1.5); await p.aclose()
asyncio.run(m())" | tee -a e3.out; fi
fi
wait $CP
echo "---- client out"; cat e3.out
echo "---- w3 log"; docker logs s0-arq-w3 2>&1 | grep -v '^$'
echo "---- w3b log"; docker logs s0-arq-w3b 2>&1 | grep -v '^$'
echo "KILLTS $KT"
docker rm -f s0-arq-w3 s0-arq-w3b >/dev/null 2>&1
