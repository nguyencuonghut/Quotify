#!/bin/bash
# remove ONLY s0-arq-* containers and the s0-arq-net network
for c in $(docker ps -a --filter "name=^s0-arq-" --format '{{.Names}}'); do docker unpause $c >/dev/null 2>&1; docker rm -f $c >/dev/null 2>&1; done
docker network rm s0-arq-net >/dev/null 2>&1
docker ps -a --filter "name=s0-arq-" --format 'leftover container: {{.Names}}'
docker network ls --filter name=s0-arq --format 'leftover network: {{.Name}}'
echo cleanup done
