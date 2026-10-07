const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const {JSDOM,VirtualConsole} = require('jsdom');
const origin=process.env.RPG_TEST_ORIGIN;
const root=path.resolve(__dirname,'..');
const clients=[],errors=[];
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const el=(dom,id)=>dom.window.document.getElementById(id);
async function until(check,label){for(let i=0;i<350;i++){if(await check())return;await pause(30);}throw new Error(label+' · '+clients.map(dom=>el(dom,'message').textContent+' / '+el(dom,'connection').textContent).join(' ; '));}
async function rpc(dom,url,body){const r=await fetch(new URL(url,origin),{method:body?'POST':'GET',headers:{Authorization:'Bearer '+dom.window.sessionStorage.getItem('rpg-token'),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw new Error(data.message);return data;}
(async()=>{
 const html=await(await fetch(origin)).text();
 const app=require('./client_source.cjs')();
 for(let index=0;index<4;index++){
  const console=new VirtualConsole();console.on('jsdomError',error=>errors.push(error.message));
  const dom=new JSDOM(html,{url:origin,runScripts:'outside-only',virtualConsole:console});clients.push(dom);
  dom.window.fetch=(url,opts)=>fetch(new URL(url,origin),opts);dom.window.crypto.randomUUID=randomUUID;dom.window.AbortController=AbortController;dom.window.AbortSignal=AbortSignal;
  dom.window.setInterval=()=>0;
  dom.window.eval(app+';window.socialTest={refresh,ready:()=>!busy&&!polling,snapshot:()=>session};');
  el(dom,'account-name').value='social_'+randomUUID().slice(0,8);el(dom,'account-password').value=randomUUID();el(dom,'name').value='Allié '+index;el(dom,'class-name').value='Knight';
  el(dom,'register-form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  await until(()=>!el(dom,'lobby').hidden,'Inscription par compte');
  await until(()=>dom.window.socialTest.ready(),'Inscription terminée');
  await rpc(dom,'/api/commands',{request_id:randomUUID(),action:'tutorial',params:{}});
  await dom.window.socialTest.refresh(true);
  await until(()=>dom.window.socialTest.snapshot()?.tutorial&&!el(dom,'character-menu').hidden,'Tutoriel affiché avant ouverture de Social');
  if(el(dom,'social-view').hidden) el(dom,'show-social').click();
  assert(!el(dom,'social-view').hidden,'Social consultable dans le jeu');
 }
 const host=clients[0];
 for(const target of clients.slice(1)){
  const name=el(target,'account-name').value;
  el(host,'social-name').value=name;el(host,'social-invite').click();
  await until(()=>host.window.socialTest.ready(),'Invitation terminée');
  await target.window.socialTest.refresh(true);
  await until(()=>el(target,'social-content').querySelector('[data-social-action="team_accept"]'),'Invitation visible');
  el(target,'social-content').querySelector('[data-social-action="team_accept"]').click();
  await until(()=>target.window.socialTest.ready(),'Acceptation terminée');
 }
 await host.window.socialTest.refresh(true);
 await until(()=>el(host,'social-capacity').textContent.includes('équipe 4/4')&&el(host,'social-content').querySelectorAll('[data-social-row^="member-"]').length===4,'Équipe complète affichée');
 assert(el(host,'social-capacity').textContent.includes('équipe 4/4'));
 assert.equal(el(host,'social-content').querySelectorAll('[data-social-row^="member-"]').length,4);
 await until(()=>el(host,'social-content').querySelector('[data-social-action="join_ally"]'),'Bouton Rejoindre affiché');
 const join=el(host,'social-content').querySelector('[data-social-action="join_ally"]');
 for(let index=0;index<8;index++)await host.window.socialTest.refresh(true);
 assert.equal(el(host,'social-content').querySelector('[data-social-action="join_ally"]'),join,'Les boutons restent stables');
 const target=clients[1];el(host,'social-name').value=el(target,'account-name').value;
 el(host,'social-search').dispatchEvent(new host.window.Event('submit',{bubbles:true,cancelable:true}));
 await until(()=>host.window.socialTest.ready(),'Demande d’ami terminée');await target.window.socialTest.refresh(true);
 await until(()=>el(target,'social-content').querySelector('[data-social-action="friend_accept"]'),'Demande d’ami affichée');
 el(target,'social-content').querySelector('[data-social-action="friend_accept"]').click();
 await until(()=>target.window.socialTest.ready(),'Amitié acceptée');await host.window.socialTest.refresh(true);
 await until(()=>el(host,'social-content').textContent.includes('Ami ·'),'Amitié affichée');
 assert(el(host,'social-content').textContent.includes('Ami ·'));
 const sessions=await Promise.all(clients.map(dom=>rpc(dom,'/api/state')));
 assert.equal(new Set(sessions.map(state=>state.session.id)).size,4,'Tutoriels indépendants');
 el(host,'choose-character-options').click();
 await until(()=>!el(host,'characters').hidden,'Choix du personnage accessible');
 assert(!host.window.document.querySelector('#copy-token'),'Aucune clé affichée');
 await until(()=>clients.every(dom=>dom.window.socialTest.ready()),'Requêtes terminées avant fermeture des fenêtres');
 assert.deepEqual(errors,[]);
 console.log('Social UI : 4 comptes, invitations après début du tutoriel, équipe 4/4, amis, boutons stables et personnages indépendants vérifiés.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const dom of clients)dom.window.close();});
