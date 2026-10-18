#!/usr/bin/env bash
# Runs on the server during a load test: every 5 s, CPU and memory (vmstat) and how fast the other
# sites on this server answer, straight from nginx. Stops by itself after $1 seconds.
#   bash monitor.sh 300 > ~/loadtest-monitor.log
end=$(( $(date +%s) + ${1:-300} ))
echo "time      cpu_us cpu_sy cpu_id cpu_wa free_mb swap_used_mb  nisatech.org  nisatak.com  contech  shop"
while [ "$(date +%s)" -lt "$end" ]; do
  read -r us sy id wa < <(vmstat 1 2 | tail -1 | awk '{print $13, $14, $15, $16}')
  free_mb=$(free -m | awk '/^Mem:/ {print $7}')
  swap=$(free -m | awk '/^Swap:/ {print $3}')
  t() { curl -s -o /dev/null -m 10 -w '%{time_total}' -H "Host: $1" -H 'X-Forwarded-Proto: https' "http://127.0.0.1$2"; }
  printf '%s %6s %6s %6s %6s %7s %12s %13s %12s %8s %6s\n' "$(date +%T)" "$us" "$sy" "$id" "$wa" "$free_mb" "$swap" \
    "$(t nisatech.org /)" "$(t nisatak.com /)" "$(t contech.nisatech.org /)" "$(t shop.nisatech.org /)"
  sleep 3
done
