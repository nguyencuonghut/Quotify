#!/bin/bash
# usage: run_e4.sh JCW STOP_TIMEOUT FN
S=/tmp/claude-1000/-run-media-cuong-DATA-02-Project-211-Theo-d-i-bi-n---ng-gi--Quotify/87e6330c-b4c9-4188-bd30-54c5b2db3564/scratchpad/s0-arq
cd $S; JCW=$1; ST=$2; FN=${3:-slow_cleanup}
docker rm -f s0-arq-w4 s0-arq-w4b >/dev/null 2>&1; docker exec s0-arq-redis redis-cli flushall >/dev/null
./startw.sh w4 JOB_TIMEOUT=100 MAX_TRIES=1 KEEP_RESULT=0 JCW=$JCW RETRY_JOBS=${RJ:-1}; sleep 1.2
docker exec -e SLEEP=${SLEEP:-60} -e FN=$FN -w /s0 s0-arq-client python e4a.py
sleep 2
T0=$(date +%s.%N); echo "$T0 HOST docker stop -t $ST (SIGTERM)"
docker stop -t $ST s0-arq-w4 >/dev/null; T1=$(date +%s.%N)
echo "HOST docker stop returned after $(awk "BEGIN{print $T1 - $T0}") s; exit code $(docker inspect s0-arq-w4 --format '{{.State.ExitCode}}') OOMKilled=$(docker inspect s0-arq-w4 --format '{{.State.OOMKilled}}')"
echo "---- w4 log"; docker logs s0-arq-w4 2>&1 | grep -v '^$'
if [ "$4" != "noprobe" ]; then ./cx e4b.py; fi
