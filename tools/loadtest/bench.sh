#!/usr/bin/env bash
# Runs on the shop's server: ApacheBench straight at a gunicorn port (no nginx, no Arvan), for the home
# page (from the page cache) and checkout (rendered every time), at rising numbers of simultaneous
# clients, with the CPU in use and gunicorn's memory. ab is one C process, so unlike origin.py it doesn't
# run out of steam before a 4-core server does (2026-10-24).
#   bash bench.sh <port> <label> [clients, default "1 8 32 64"] [seconds per step, default 15]
# Needs apache2-utils. Like nginx, ab opens a new connection for each request (no keep-alive).
port=$1
label=$2
clients=${3:-1 8 32 64}
secs=${4:-15}
for path in / /checkout/; do
  for c in $clients; do
    vmstat 1 $((secs + 1)) > /tmp/bench-vm.$$ &
    out=$(ab -q -c "$c" -t "$secs" -n 10000000 -s 30 -H 'Host: penolinshop.com' -H 'X-Forwarded-Proto: https' \
      -H 'User-Agent: purseshop-loadtest/1 (Nisatech, bench)' "http://127.0.0.1:$port$path" 2>&1)
    wait
    get() { echo "$out" | awk -v k="$1" -v f="$2" 'index($0, k) == 1 {print $f; exit}'; }
    idle=$(tail -n "$secs" /tmp/bench-vm.$$ | awk '{s += $15} END {printf "%d", s / NR}')
    printf '%-14s %-10s c=%-3s %8s req/s  p50 %5s ms  p95 %5s ms  failed %s  non-2xx %s  cpu %3s%%\n' \
      "$label" "$path" "$c" "$(get 'Requests per second' 4)" "$(get '  50%' 2)" "$(get '  95%' 2)" \
      "$(get 'Failed requests' 3)" "$(get 'Non-2xx responses' 3)" "$((100 - idle))"
  done
done
rm -f /tmp/bench-vm.$$
echo "$label gunicorn memory: $(ps -o rss= -C gunicorn | awk '{s += $1} END {printf "%d MB in %d processes", s / 1024, NR}')"
