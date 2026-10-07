const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {JSDOM} = require(require.resolve('jsdom', {paths: [path.join(__dirname, '..', '.ui-test'), __dirname]}));
const root = path.join(__dirname, '..');
const webAppSource = require('./web_app_source.cjs');
const fixture = spawnSync(process.env.PYTHON || 'python', ['-c', `
import json
from jeuxRPG.multiplayer import tutorial, fields, content
from jeuxRPG.multiplayer.service import GameError
p = tutorial.new_party([{'id':'p', 'name':'Test', 'class_name':'Knight'}])
p['step'] = 'road'
fields.enter(p, 'rosee', [30,20], 0)
def snapshot(revision):
    view = tutorial.view(p, 'p', 0)
    return {'id':'room', 'me':'p', 'state':'running', 'revision':revision, 'players':view['players'], 'events':[], 'tutorial':view}
far = snapshot(1)
p['battle']['players']['p']['position'] = [32,20]
near = snapshot(2)
messages, _ = tutorial.execute(p, 'p', 'talk', {'npc':'mira'}, 0, GameError, lambda:.5)
active = snapshot(3)
active['events'] = [{'id':1, 'game_time':0, 'message':messages[-1]}]
p['kills'] = content.HUNT['count'] + 1
ready = snapshot(4)
messages, _ = tutorial.execute(p, 'p', 'talk', {'npc':'mira'}, 0, GameError, lambda:.5)
completed = snapshot(5)
completed['events'] = [{'id':2, 'game_time':0, 'message':messages[-1]}]
print(json.dumps({'far':far, 'near':near, 'active':active, 'ready':ready, 'completed':completed}))
`], {cwd: root, encoding:'utf8'});
assert.equal(fixture.status, 0, fixture.stderr);
const states = JSON.parse(fixture.stdout);
const dom = new JSDOM(fs.readFileSync(path.join(root, 'jeuxRPG/multiplayer/web/index.html'), 'utf8'), {url:'https://rpg.test', runScripts:'outside-only'});
const w = dom.window;
const get = id => w.document.getElementById(id);
const calls = [];
let current = states.near;
w.structuredClone = structuredClone;
w.setInterval = () => 0;
w.fetch = async (url, options) => {
  let data = {};
  if (url === '/api/classes') data = {classes:[]};
  if (url === '/api/commands') {
    const body = JSON.parse(options.body);
    calls.push(body);
    assert.equal(body.action, 'talk');
    assert.equal(body.params.npc, 'mira');
    assert.equal(body.params.world_context, current.tutorial.world_context);
    assert.equal(options.headers['X-RPG-Command-Ack'], undefined);
    current = current.tutorial.quest === 'unaccepted' ? states.active : states.completed;
    data = {session:current};
  }
  if (url === '/api/state') data = {session:current};
  return {ok:true, json:async () => data};
};
w.eval(fs.readFileSync(path.join(root, 'jeuxRPG/multiplayer/web/map_artwork.js'), 'utf8'));
w.eval(webAppSource(root) + ';window.mount = value => {token="test"; session=value; sessionId=value.id; renderTutorial(value.tutorial);}; window.ready = () => !busy; window.stubMovement = () => {const original = moveControlled; moveControlled = (adventure, me, destination) => {window.touchDestination = destination;}; return () => {moveControlled = original;};};');
async function waitFor(check) {
  for (let i=0; i<100; i++) { if (check()) return; await new Promise(resolve => setTimeout(resolve, 10)); }
  throw new Error('Dialogue de Mira bloqué');
}
(async () => {
  w.mount(states.far);
  const mira = () => get('world-map').querySelector('[data-site="mira"]');
  assert(mira());
  mira().dispatchEvent(new w.MouseEvent('click', {bubbles:true}));
  assert.equal(calls.length, 0);
  assert.match(get('message').textContent, /Approchez-vous de Mira/);
  assert.equal(get('message').parentElement.id, 'combat-action-panel');
  assert.equal(get('field-move-selected').disabled, false);
  const restoreMovement = w.stubMovement();
  get('field-move-selected').click();
  assert.deepEqual(Array.from(w.touchDestination), [32,20]);
  restoreMovement();
  w.mount(states.near);
  assert.equal(get('npc-view').hidden, false);
  assert.equal(get('npc-actions').textContent, 'Accepter la quête');
  assert.equal(get('quest-view').parentElement.className, 'dashboard-box quest-box');
  mira().dispatchEvent(new w.MouseEvent('click', {bubbles:true}));
  await waitFor(() => w.ready() && /gobelins vaincus/.test(get('quest-progress').textContent));
  assert.equal(calls.length, 1);
  assert.match(get('quest-description').textContent, /Objectif : 10 gobelin/);
  assert.match(get('npc-dialogue').textContent, /reste 10 gobelin/);
  assert.match(get('message').textContent, /Mira/);
  w.mount(states.ready);
  assert.equal(get('npc-actions').textContent, 'Rendre la quête');
  assert.match(get('npc-dialogue').textContent, /vaincu les 10 gobelins/);
  get('npc-actions').querySelector('button').click();
  await waitFor(() => w.ready() && /accomplie/.test(get('quest-progress').textContent));
  assert.equal(calls.length, 2);
  assert.match(get('forge-status').textContent, /Forge débloquée/);
  assert.match(get('message').textContent, /750 XP/);
  assert.equal(w.document.querySelectorAll('[style]').length, 0);
  dom.window.close();
  console.log('Mira : proximité, acceptation, objectif visible et remise de quête vérifiés.');
})().catch(error => {dom.window.close(); console.error(error); process.exitCode=1;});
