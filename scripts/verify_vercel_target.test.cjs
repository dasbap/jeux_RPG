const {test} = require('node:test');
const assert = require('node:assert/strict');
const {verifiedOrigin,safeMessage,scopedHeaders} = require('./verify_vercel_preview.cjs');
const release = 'a'.repeat(40);
const preview = {projectId:'prj_fVH6vG7RCXf5OP3MIfTngxeCN8U2',ownerId:'team_qde9V6kikwwSvLtNrjAsAkRY',target:null,readyState:'READY',meta:{githubCommitSha:release},url:'jeux-preview-dasbaps-projects.vercel.app'};
test('credentials are scoped to the authenticated preview metadata', () => {
  assert.equal(verifiedOrigin(preview,release),'https://'+preview.url);
  for(const patch of [{projectId:'other'},{ownerId:'other'},{target:'production'},{target:undefined},{target:'development'},{readyState:'ERROR'},{meta:{githubCommitSha:'b'.repeat(40)}},{url:'attacker.invalid'},{url:preview.url+'/path'}]) {
    assert.throws(()=>verifiedOrigin({...preview,...patch},release));
  }
});
test('browser failures never print HTTP authentication call logs',()=>{
  assert.equal(safeMessage(new Error('route.fetch: failed\n - authorization: Bearer private-value\n - x-vercel-trusted-oidc-idp-token: eyJfake.payload.signature')),'route.fetch: failed');
  assert(!safeMessage('Rejected Bearer private-value').includes('private-value'));
  assert(!safeMessage('Rejected eyJfake.payload.signature').includes('eyJfake'));
});
test('temporary preview authentication never follows foreign HTTP origins',()=>{
 const base='https://jeux-preview-dasbaps-projects.vercel.app',key='x-vercel-trusted-oidc-idp-token';
 const auth={[key]:'private-fixture'};
 assert.equal(scopedHeaders({},base+'/api/state',base,auth)[key],'private-fixture');
 assert(!Object.values(scopedHeaders(auth,'https://cdn.jsdelivr.net/file.js',base,auth)).includes('private-fixture'));
});
