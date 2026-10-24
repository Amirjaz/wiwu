// Ramped load test through the real path (ArvanCloud -> nginx -> gunicorn). Each stage runs N
// simultaneous visitors with no pause between requests, for a fixed time, on a mix of the pages
// people open. Stops at the first sign of trouble.
//   node ramp.mjs <base> '[1,2,5,10,20,40]' <seconds-per-stage>
const BASE = process.argv[2] ?? 'https://penolinshop.com';
const STAGES = JSON.parse(process.argv[3] ?? '[1,2,5,10,20,40]');
const SECS = Number(process.argv[4] ?? 30);
const MIX = [['/', 0.7], ['/checkout/', 0.15], ['/orders/', 0.1], ['/p/returns/', 0.05]];

const pick = () => {
  let r = Math.random();
  for (const [path, share] of MIX) if ((r -= share) <= 0) return path;
  return '/';
};
const pct = (sorted, p) => sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] : 0;

async function visitor(stats, until) {
  while (Date.now() < until) {
    const path = pick();
    const t0 = performance.now();
    try {
      const res = await fetch(BASE + path, { headers: { 'user-agent': 'purseshop-loadtest/1 (Nisatech)' } });
      const body = await res.arrayBuffer();
      stats.bytes += body.byteLength;
      stats.codes[res.status] = (stats.codes[res.status] ?? 0) + 1;
      if (res.status >= 400) stats.errors++;
      else stats.lat.push(performance.now() - t0);
    } catch (error) {
      stats.codes.ERR = (stats.codes.ERR ?? 0) + 1;
      stats.errors++;
    }
  }
}

console.log('stage  users  req/s   p50ms  p95ms  p99ms  maxms  errors  KB/s  codes');
for (const users of STAGES) {
  const stats = { lat: [], errors: 0, bytes: 0, codes: {} };
  const until = Date.now() + SECS * 1000;
  const t0 = performance.now();
  await Promise.all(Array.from({ length: users }, () => visitor(stats, until)));
  const secs = (performance.now() - t0) / 1000;
  const lat = stats.lat.sort((a, b) => a - b);
  const total = lat.length + stats.errors;
  const errRate = total ? stats.errors / total : 1;
  console.log([
    new Date().toISOString().slice(11, 19), String(users).padStart(5), (total / secs).toFixed(1).padStart(6),
    pct(lat, 0.5).toFixed(0).padStart(7), pct(lat, 0.95).toFixed(0).padStart(6), pct(lat, 0.99).toFixed(0).padStart(6),
    (lat.at(-1) ?? 0).toFixed(0).padStart(6), `${stats.errors}`.padStart(7), (stats.bytes / 1024 / secs).toFixed(0).padStart(5),
    JSON.stringify(stats.codes),
  ].join(' '));
  const blocked = ['403', '429', '503'].some((code) => stats.codes[code]);
  if ((stats.errors >= 5 && errRate > 0.02) || pct(lat, 0.95) > 4000 || blocked) {
    console.log(`stopping: ${blocked ? 'blocked or overloaded responses' : errRate > 0.02 ? 'error rate over 2%' : 'p95 over 4 s'}`);
    break;
  }
}
