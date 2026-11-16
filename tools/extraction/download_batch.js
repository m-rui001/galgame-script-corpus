const fs = require('fs');
const path = require('path');
const ids = fs.readFileSync(process.argv[2], 'utf8').trim().split(/\s+/).map(Number).filter(Boolean);
const OUTDIR = 'D:/mxrlib/_patches';
const META = 'D:/mxrlib/_audit/patch_meta.jsonl';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36';
const CONC = 3;
const known = new Set();
if (fs.existsSync(META)) for (const l of fs.readFileSync(META, 'utf8').trim().split('\n')) {
  try { known.add(JSON.parse(l).id); } catch {}
}
const queue = ids.filter(id => !known.has(id));
const metaOut = fs.createWriteStream(META, { flags: 'a' });
let idx = 0;

async function getJson(url, tries = 5) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'user-agent': UA, accept: 'application/json' } });
      if (r.ok) return await r.json();
      await new Promise(s => setTimeout(s, 1500 * (i + 1)));
    } catch { await new Promise(s => setTimeout(s, 1500 * (i + 1))); }
  }
  return null;
}

async function download(url, dest, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'user-agent': UA } });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const buf = Buffer.from(await r.arrayBuffer());
      fs.writeFileSync(dest, buf);
      return buf.length;
    } catch (e) {
      if (i === tries - 1) throw e;
      await new Promise(s => setTimeout(s, 3000 * (i + 1)));
    }
  }
}

async function worker() {
  while (true) {
    const i = idx++;
    if (i >= queue.length) return;
    const id = queue[i];
    const j = await getJson(`https://www.moyu.moe/api/v1/resource/${id}`);
    if (!j || !j.data || !j.data.resource || !j.data.resource.download_url) {
      console.log('FAIL_META', id);
      continue;
    }
    const r = j.data.resource;
    const p = r.patch || {};
    const dest = path.join(OUTDIR, id + '.zip');
    let size = 0;
    if (fs.existsSync(dest)) size = fs.statSync(dest).size;
    else {
      try { size = await download(r.download_url, dest); }
      catch (e) { console.log('FAIL_DL', id, e.message); continue; }
    }
    metaOut.write(JSON.stringify({
      id, name: r.name, size: r.size, type: r.type, language: r.language,
      model: r.model_name, group: r.localization_group_name, note: (r.note || '').slice(0, 2000),
      download_url: r.download_url, zip_bytes: size,
      patch: p.name || null, patch_id: p.id || null, vndb: p.vndb_id || null,
      galgame_id: r.galgame_id, created: r.created, updated: r.updated
    }) + '\n');
    console.log('OK', id, (size / 1048576).toFixed(1) + 'MB', r.name.slice(0, 40));
  }
}
Promise.all(Array.from({ length: CONC }, worker)).then(() => { metaOut.end(); console.log('done'); });
