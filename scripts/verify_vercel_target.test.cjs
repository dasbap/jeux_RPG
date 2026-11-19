const {test} = require('node:test');
const assert = require('node:assert/strict');
const {verifiedOrigin} = require('./verify_vercel_preview.cjs');
const release = 'a'.repeat(40);
const preview = {projectId:'prj_fVH6vG7RCXf5OP3MIfTngxeCN8U2',ownerId:'team_qde9V6kikwwSvLtNrjAsAkRY',target:null,readyState:'READY',meta:{githubCommitSha:release},url:'jeux-preview-dasbaps-projects.vercel.app'};
test('credentials are scoped to the authenticated preview metadata', () => {
  assert.equal(verifiedOrigin(preview,release),'https://'+preview.url);
  for(const patch of [{projectId:'other'},{ownerId:'other'},{target:'production'},{target:undefined},{target:'development'},{readyState:'ERROR'},{meta:{githubCommitSha:'b'.repeat(40)}},{url:'attacker.invalid'},{url:preview.url+'/path'}]) {
    assert.throws(()=>verifiedOrigin({...preview,...patch},release));
  }
});
