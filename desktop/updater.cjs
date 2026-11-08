'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {Readable, Transform} = require('node:stream');
const {pipeline} = require('node:stream/promises');
const {selectUpdate, RELEASE_API} = require('./generated/ui/release.js');

function createUpdater({net, app, shell}) {
 let pending, active;
 return {
  async check() {
   const response = await net.fetch(RELEASE_API, {redirect:'error', signal:AbortSignal.timeout(12000)});
   if (!response.ok) throw new Error('GitHub update check failed');
   pending = selectUpdate(await response.json(), app.getVersion(), 'desktop');
   return pending;
  },
  install(version) {
   if (active) throw new Error('An update is already downloading');
   if (!app.isPackaged || !pending || pending.version !== version) throw new Error('Check for updates first');
   const asset = pending;
   active = (async () => {
    const folder = await fs.promises.mkdtemp(path.join(app.getPath('temp'), 'nyxor-update-'));
    const file = path.join(folder, asset.name);
    try {
     const signal = AbortSignal.timeout(300000);
     const response = await net.fetch(asset.url, {signal});
     if (!response.ok || !response.body) throw new Error('Update download failed');
     const hash = createHash('sha256');
     let size = 0;
     const verify = new Transform({transform(chunk, _encoding, callback) {
      size += chunk.length;
      if (size > asset.size) return callback(new Error('Unexpected update size'));
      hash.update(chunk);
      callback(null, chunk);
     }});
     await pipeline(Readable.fromWeb(response.body), verify, fs.createWriteStream(file, {flags:'wx'}), {signal});
     if (size !== asset.size || hash.digest('hex') !== asset.digest) throw new Error('Update integrity check failed');
     const error = await shell.openPath(file);
     if (error) throw new Error('Could not open the verified installer');
    } catch (error) {
     await fs.promises.unlink(file).catch(() => {});
     await fs.promises.rmdir(folder).catch(() => {});
     throw error;
    }
   })().finally(() => { active = null; });
   return active;
  }
 };
}
module.exports = {createUpdater};
