'use strict';

const RELEASE_API = 'https://api.github.com/repos/ThunderBoldX/NYXOR/releases/latest';
const RELEASE_DOWNLOAD = 'https://github.com/ThunderBoldX/NYXOR/releases/download/';
const TARGETS = {desktop: ['Windows', 'exe'], android: ['Android', 'apk']};

function selectUpdate(release, installed, platform) {
 const target = TARGETS[platform];
 const tag = /^v(\d{1,6}\.\d{1,6}\.\d{1,6})$/.exec(release?.tag_name || '');
 const current = /^(\d{1,6}\.\d{1,6}\.\d{1,6})(?:-preview)?$/.exec(installed);
 if (!target || !tag || !current || release.draft || release.prerelease) return null;
 const version = tag[1];
 const next = version.split('.').map(Number), previous = current[1].split('.').map(Number);
 const difference = next.map((value, index) => value - previous[index]).find(Boolean);
 if (!(difference > 0)) return null;
 const name = `NYXOR-${target[0]}-${version}.${target[1]}`;
 const url = RELEASE_DOWNLOAD + tag[0] + '/' + name;
 const matches = (Array.isArray(release.assets) ? release.assets : []).filter(asset =>
  asset.name === name && asset.browser_download_url === url && asset.state === 'uploaded');
 if (matches.length !== 1) return null;
 const asset = matches[0];
 if (!/^sha256:[a-f0-9]{64}$/.test(asset.digest || '') ||
     !Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > 512 * 1024 * 1024) return null;
 return {version, name, url, digest: asset.digest.slice(7), size: asset.size};
}
if (typeof module === 'object') module.exports = {selectUpdate, RELEASE_API};
