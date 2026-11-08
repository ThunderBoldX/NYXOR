'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {selectUpdate} = require('../../android/app/src/main/assets/frontend/release.js');

test('one release chooses the canonical installer for the current platform', () => {
 const tag_name = 'v2.4.10';
 const assets = ['NYXOR-Android-2.4.10.apk', 'NYXOR-Windows-2.4.10.exe'].map(name => ({
  name, size:42, state:'uploaded', digest:'sha256:'+'a'.repeat(64),
  browser_download_url:'https://github.com/ThunderBoldX/NYXOR/releases/download/'+tag_name+'/'+name
 }));
 const release = {tag_name, assets};
 assert.equal(selectUpdate(release,'2.4.9','desktop').name,assets[1].name);
 assert.equal(selectUpdate(release,'2.4.4-preview','android').name,assets[0].name);
 assert.equal(selectUpdate(release,'2.4.10','desktop'),null);
 assert.equal(selectUpdate({...release,prerelease:true},'2.4.9','android'),null);
 assert.equal(selectUpdate({...release,assets:[assets[1]]},'2.4.9','android'),null);
 assert.equal(selectUpdate({...release,assets:[{...assets[1],browser_download_url:'https://example.com/payload.exe'}]},'2.4.9','desktop'),null);
});
