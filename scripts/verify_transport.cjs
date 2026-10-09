const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../jeuxRPG/multiplayer/web/realtime.js'), 'utf8');
function setup(WebSocket) {
  const calls = [];
  const context = {WebSocket, location: new URL('https://game.vercel.app/'), URL, document: {hidden:false, addEventListener(){}},
    fetch: async (path, options) => { calls.push({path, options}); return {ok:true, status:200, json:async()=>({ok:true})}; },
    setTimeout: () => 1, clearTimeout(){}, setInterval: () => 1, clearInterval(){}, structuredClone};
  vm.createContext(context); vm.runInContext(source, context);
  return {transport:context.rpgRealtime, calls};
}
class Blocked { static OPEN = 1; constructor() {throw new Error('Blocked');} }
class Socket {
  static OPEN = 1;
  constructor() {this.readyState=0;this.events={};Socket.last=this;queueMicrotask(()=>{this.readyState=1;this.emit('open');});}
  addEventListener(type, handler) {this.events[type]=handler;}
  emit(type, event={}) {this.events[type]?.(event);}
  send(raw) {
    const item = JSON.parse(raw);
    if (item.type === 'authenticate') {this.authentication=item;queueMicrotask(()=>this.emit('message',{data:JSON.stringify({type:'authenticated'})}));}
    else if (item.id) {this.lastRequest=item; if(this.drop) this.close(); else queueMicrotask(()=>this.emit('message',{data:JSON.stringify({id:item.id,result:{status:200,body:{ok:true}}})}));}
  }
  close() {this.readyState=3;queueMicrotask(()=>this.emit('close'));}
}
(async () => {
  const blocked = setup(Blocked);
  await blocked.transport.request('/api/state', {headers:{Authorization:'Bearer token'}});
  assert.equal(blocked.calls.length,1);
  assert.equal(blocked.transport.connected,false);
  const active = setup(Socket);
  await active.transport.request('/api/account/login', {method:'POST',body:'{}'});
  assert.equal(active.calls.length,1);
  await active.transport.request('/api/state', {headers:{Authorization:'Bearer token'}});
  assert.equal(Socket.last.authentication.headers.Authorization,'Bearer token');
  assert.equal(active.transport.connected,true);
  assert.equal(active.calls.length,1);
  await active.transport.request('/api/state', {headers:{Authorization:'Bearer changed'}});
  assert.equal(Socket.last.authentication.headers.Authorization,'Bearer changed');
  assert.equal(active.transport.connected,true);
  Socket.last.drop=true;
  const options={method:'POST',headers:{Authorization:'Bearer changed'},body:JSON.stringify({request_id:'same-id',action:'rest',params:{}})};
  await active.transport.request('/api/commands',options);
  assert.equal(active.calls.length,2);
  assert.equal(active.calls[1].options.body,options.body);
  assert.equal(active.transport.connected,false);
  await active.transport.request('/api/state', {headers:{Authorization:'Bearer changed'}});
  Socket.last.drop=true;
  await assert.rejects(active.transport.request('/api/social', {method:'POST',headers:{Authorization:'Bearer changed'},body:'{}'}));
  assert.equal(active.calls.length,2);
  console.log('Transport : connexion bloquée, authentification, repli HTTP et rejouabilité des commandes vérifiés.');
})().catch(error=>{console.error(error);process.exitCode=1;});
