'use strict';
const http = require('node:http');
const os = require('node:os');
const fs = require('node:fs');
const path = require('node:path');
const {randomBytes, createHmac, timingSafeEqual} = require('node:crypto');

function addresses() {
 return [...new Set(Object.values(os.networkInterfaces()).flat().filter(item =>
  item.family === 'IPv4' && !item.internal &&
  /^(?:10[.]|192[.]168[.]|172[.](?:1[6-9]|2[0-9]|3[01])[.])/.test(item.address)
 ).map(item => item.address))];
}

function publicSnapshot(data) {
 const settings = data?.settings || {};
 const points = settings.channel_points || {};
 return {
  running: data?.running === true || (data?.accounts || []).some(account => account.running),
  profile: {
   queue: data?.queue || [], streamers: data?.streamers || [], points_games: data?.points_games || [],
   points_order: settings.points_order || 'popular',
   auto_restart: settings.auto_restart !== false, energy_saver: settings.energy_saver === true,
   enabled: points.enabled !== false, auto_claim_bonus: points.auto_claim_bonus !== false,
   follow_raids: points.follow_raids === true, claim_moments: points.claim_moments === true
  }
 };
}

function createDeviceLink(root, snapshot) {
 const file = path.join(root, 'device-link.json');
 const nonces = new Map();
 let server, code, peer, seen = 0, operation = Promise.resolve();
 const status = () => ({addresses:addresses(), linked:Boolean(code), code:code || '',
  peer:Date.now()-seen<45000 ? peer : null});
 async function close() {
  code = null; peer = null; seen = 0; nonces.clear();
  if (server) {
   const previous = server;
   server = null;
   await new Promise(resolve => {previous.close(resolve);previous.closeAllConnections();});
  }
 }
 async function start(address, secret, port = 0) {
  if (!addresses().includes(address) || !/^[a-f0-9]{64}$/.test(secret)) throw new Error('Select a local network address');
  await close();
  const key = Buffer.from(secret, 'hex');
  server = http.createServer({requestTimeout:5000, headersTimeout:5000}, async (req,res) => {
   try {
    const nonce = req.headers['x-nyxor-nonce'], mac = req.headers['x-nyxor-mac'];
    if (req.method !== 'POST' || req.url !== '/nyxor/v1' ||
        !/^\d{10}[.][a-f0-9]{32}$/.test(nonce || '') || !/^[a-f0-9]{64}$/.test(mac || '')) {
     res.writeHead(403).end(); return;
    }
    const now = Date.now();
    if (Math.abs(now - Number(nonce.split('.')[0])*1000)>60000 || nonces.has(nonce)) {
     res.writeHead(403).end(); return;
    }
    const sign = (label,body) => createHmac('sha256',key).update(label+':'+nonce+':').update(body).digest();
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
     size += chunk.length;
     if (size>64000) {res.writeHead(413).end();return;}
     chunks.push(chunk);
    }
    const body = Buffer.concat(chunks);
    if (!timingSafeEqual(Buffer.from(mac,'hex'),sign('phone',body)) || nonces.has(nonce)) {
     res.writeHead(403).end();return;
    }
    for (const [value, time] of nonces) if (now-time>125000) nonces.delete(value);
    if (nonces.size>=256) {res.writeHead(429).end();return;}
    nonces.set(nonce,now);
    const data = JSON.parse(body);
    if (typeof data.running !== 'boolean' || !data.profile || typeof data.profile !== 'object') throw new Error('Invalid snapshot');
    peer = {running:data.running, profile:data.profile};seen = now;
    const result = Buffer.from(JSON.stringify(publicSnapshot(snapshot())));
    res.writeHead(200,{'Content-Type':'application/json','X-Nyxor-Mac':sign('pc',result).toString('hex')}).end(result);
   } catch { if (!res.headersSent) res.writeHead(400).end(); }
  });
  await new Promise((resolve,reject) => {
   server.once('error',reject);
   server.listen(port,address,()=>{server.removeListener('error',reject);resolve();});
  });
  server.maxConnections=16;
  server.setTimeout(6000,socket=>socket.destroy());
  server.on('error',()=>{void close();});
  code = address+':'+server.address().port+'#'+secret;
 }
 return {
  async restore() {
   try {
    const {address,secret,port} = JSON.parse(fs.readFileSync(file,'utf8'));
    await start(address,secret,port);
   } catch { await close(); }
  },
  handle(data) {
   const task = operation.then(async () => {
   if (data.action === 'device_offer') {
    const secret = randomBytes(32).toString('hex');
    await start(data.address,secret);
    try {fs.writeFileSync(file,JSON.stringify({address:data.address,secret,port:server.address().port}));}
    catch(error){await close();throw error;}
   } else if (data.action === 'device_unlink') {
    await close();
    fs.rmSync(file,{force:true});
   }
    return status();
   });
   operation = task.catch(() => {});
   return task;
  },
  close
 };
}
module.exports = {createDeviceLink};
