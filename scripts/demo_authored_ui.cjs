const assert = require('node:assert/strict');
const {randomUUID} = require('node:crypto');
const {JSDOM, VirtualConsole} = require('jsdom');
const origin = process.env.RPG_TEST_ORIGIN;
const clients = [], errors = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const $ = (dom, id) => dom.window.document.getElementById(id);
const state = dom => dom.window.demoSnapshot();
const visible = node => node && !node.disabled && !node.closest('[hidden]');
function press(dom, selector, match = () => true) {
  const node = [...dom.window.document.querySelectorAll(selector)].find(node => visible(node) && match(node));
  if (!node) return false;
  node.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true}));
  return true;
}
function double(dom, node) {
  if (!node) return false;
  node.dispatchEvent(new dom.window.MouseEvent('dblclick', {bubbles:true, cancelable:true}));
  return true;
}
async function wait(condition, label, duration=15000) {
  const until = Date.now()+duration;
  while (Date.now()<until) { if (condition()) return; await pause(100); }
  throw new Error(`${label} : ${clients.map(dom => $(dom,'message')?.textContent).join(' · ')}`);
}
async function client(name, className) {
  const html = await (await fetch(origin)).text();
  const js = await (await fetch(origin+'/map_artwork.js')).text()+'\n'+await (await fetch(origin+'/app.js')).text();
  const console = new VirtualConsole();
  console.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(html, {url:origin,runScripts:'outside-only',virtualConsole:console});
  clients.push(dom);
  const interval=dom.window.setInterval.bind(dom.window); dom.timers=[];
  dom.window.setInterval=(...args)=>{const timer=interval(...args);dom.timers.push(timer);return timer;};
  dom.actions=[];
  dom.window.fetch = (url, options) => { if(String(url).includes('/api/commands')) { const body=JSON.parse(options.body); dom.actions.push({action:body.action,params:body.params}); } return fetch(new URL(url, origin), options); };
  dom.window.AbortController = AbortController;
  dom.window.AbortSignal = AbortSignal;
  dom.window.crypto.randomUUID = randomUUID;
  dom.window.eval(js+';window.demoSnapshot = () => session; window.demoPath = gridPath; window.demoIdle=()=>!busy&&!polling; window.demoReady=()=>!busy;');
  $(dom,'name').value = name;
  $(dom,'class-name').value = className;
  $(dom,'register-form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  await wait(()=>!$(dom,'lobby').hidden,'inscription');
  return dom;
}
function walk(dom, target) {
  const s=state(dom), a=s.tutorial, unit=a.battle.players[s.me];
  if (unit.route.length) return false;
  const route=dom.window.demoPath(a.battle.map,unit.position,target);
  if (!route) throw new Error(`Chemin inaccessible ${a.field_map}: ${target}`);
  if (!route.length) return false;
  const point=[...route].reverse().find(p=>dom.window.document.querySelector(`[data-cell="${p}"]`));
  if (!point) return false;
  return double(dom,dom.window.document.querySelector(`[data-cell="${point}"]`));
}
function support(dom) {
  const s=state(dom), a=s?.tutorial;
  if (!a?.battle || !dom.window.demoReady()) return false;
  const me=a.players.find(p=>p.id===s.me);
  const injured=a.players.filter(p=>p.hp<p.max_hp*.75).sort((x,y)=>x.hp/x.max_hp-y.hp/y.max_hp)[0];
  const heal=injured && me.skills.find(k=>k.type==='HEAL' && k.available && k.targets.includes(injured.id));
  const enemy=a.mobs.filter(m=>Math.hypot(...m.position.map((n,i)=>n-a.battle.players[s.me].position[i]))<=me.attack_range).sort((x,y)=>x.stats.hp.current-y.stats.hp.current)[0];
  const leader=a.players.find(p=>p.id!==s.me);
  if (!heal && leader && !a.battle.players[s.me].route.length && Math.hypot(...a.battle.players[s.me].position.map((n,i)=>n-a.battle.players[leader.id].position[i]))>3) { double(dom,dom.window.document.querySelector(`[data-unit="${leader.id}"]`)); return false; }
  const target=heal ? injured.id : enemy?.combat_id;
  if(target) {
    const node=dom.window.document.querySelector(`[data-unit="${target}"]`);
    if(node && $(dom,'combat-target').value!==target) node.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true}));
    if(heal && press(dom,'#skills button',b=>b.textContent.startsWith(heal.name))) return true;
    if(!heal && press(dom,'#combat-actions button',b=>b.textContent.startsWith('Attaque simple'))) return true;
  }
  return false;
}

async function runUntil(dom, predicate, label, target, limit=600000) {
  console.log(label);
  const deadline=Date.now()+limit;
  let report=0;
  while(Date.now()<deadline) {
    const s=state(dom), a=s.tutorial;
    if(predicate(a)) return;
    if(!dom.window.demoReady()) { await pause(100); continue; }
    if(clients.some(ally=>ally!==dom && support(ally))) { await pause(200); continue; }
    const me=a.players.find(p=>p.id===s.me);
    if(Date.now()>report) { console.log(JSON.stringify({lieu:a.field_map||a.position,pv:me.hp,kills:a.kills,position:a.battle?.players[s.me].position,mobs:a.mobs.map(m=>({id:m.combat_id,hp:m.stats.hp.current})),action:dom.actions.at(-1)?.action,message:$(dom,'message').textContent})); report=Date.now()+10000; }
    if(me.hp<=0) { await pause(150); continue; }
    if(a.battle) {
      const unit=a.battle.players[s.me];
      const distance=m=>Math.hypot(...m.position.map((n,i)=>n-unit.position[i]));
      const enemies=a.mobs.filter(m=>m.stats.hp.current>0).sort((x,y)=>distance(x)-distance(y)||x.stats.hp.current-y.stats.hp.current);
      const enemy=enemies[0];
      if(enemy && (enemies.filter(m=>distance(m)<6).length>2 || me.hp<me.max_hp*.65) && distance(enemy)<4) {
        const map=a.battle.map;
        const candidates=[[5,0],[-5,0],[0,5],[0,-5],[4,4],[4,-4],[-4,4],[-4,-4]].map(([dx,dy])=>[Math.max(0,Math.min(map.width-1,unit.position[0]+dx)),Math.max(0,Math.min(map.height-1,unit.position[1]+dy))]).filter(p=>dom.window.document.querySelector(`[data-cell="${p}"]`) && dom.window.demoPath(map,unit.position,p)?.length);
        candidates.sort((x,y)=>Math.min(...enemies.map(m=>Math.hypot(...m.position.map((n,i)=>n-y[i]))))-Math.min(...enemies.map(m=>Math.hypot(...m.position.map((n,i)=>n-x[i])))));
        if(candidates[0]) { walk(dom,candidates[0]); await pause(150); continue; }
      }
      if(enemy) {
        const node=dom.window.document.querySelector(`[data-unit="${enemy.combat_id}"]`);
        if(node && $(dom,'combat-target').value!==enemy.combat_id) node.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true}));
        if(!press(dom,'#skills button',b=>!b.textContent.includes('Heal')) && !press(dom,'#combat-actions button',b=>b.textContent.startsWith('Attaque simple'))) walk(dom,enemy.position);
      } else {
        const corpse=a.battle.corpses.find(c=>!c.harvested.length);
        if(corpse) {
          if(!press(dom,'#corpse-actions button',b=>!b.textContent.includes('déjà'))) walk(dom,corpse.position);
        } else if(target) await target(a);
        else {
          const unseen=(a.battle.map.spawns||[]).find(p=>!(a.battle.explored||[]).some(q=>q.join()===p.join()));
          if(unseen) walk(dom,unseen);
          else throw new Error(`${label}: aucun ennemi ni objectif accessible`);
        }
      }
    } else if(!a.moving && target) await target(a);
    await pause(150);
  }
  throw new Error(`${label}: délai dépassé · ${$(dom,'message').textContent} · ${JSON.stringify(state(dom).tutorial.position)}`);
}
function exitTo(dom,destination) {
  const a=state(dom).tutorial;
  if(a.battle.players[state(dom).me].route.length) return;
  if(!a.field_map) return double(dom,dom.window.document.querySelector('[data-exit]'));
  const gate=a.battle.map.exits.find(g=>g.destination===destination);
  if(!gate) throw new Error(`Sortie vers ${destination} absente de ${a.field_map}`);
  double(dom,dom.window.document.querySelector(`[data-exit="${gate.position}"]`));
}
function travel(dom,destination) {
  press(dom,'#show-map');
  const a=state(dom).tutorial;
  const parent=a.world.places.find(place=>place.points.some(point=>point.id===destination));
  if(parent) { const node=dom.window.document.querySelector(`[data-destination="${parent.id}"]`); if(node) node.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true})); }
  return double(dom,dom.window.document.querySelector(`[data-destination="${destination}"], [data-point="${destination}"]`));
}
async function main() {
  try {
    const hero=await client('Démo chevalier','Knight'), healer=await client('Démo soutien','Priest');
    press(hero,'#create');
    await wait(()=>!$(hero,'invitation').hidden,'invitation');
    $(healer,'invite-input').value=$(hero,'invite-link').value;
    $(healer,'join-form').dispatchEvent(new healer.window.Event('submit',{bubbles:true,cancelable:true}));
    await wait(()=>!$(hero,'party-tutorial').disabled,'groupe');
    press(hero,'#party-tutorial');
    await wait(()=>state(hero)?.tutorial,'tutoriel');
    await runUntil(hero,a=>a.field_map==='forest','Clairière : combat, dépeçage et chemin vers la forêt',()=>exitTo(hero,'forest'));
    await runUntil(hero,a=>!a.battle,'Forêt : exploration et sortie vers les chemins rapides',()=>exitTo(hero,null));
    await runUntil(hero,a=>a.field_map==='rosee','Déplacement rapide vers Rosée',()=>travel(hero,'rosee'));
    await runUntil(hero,a=>a.quest==='active','Place du village et acceptation de la quête',a=>{
      const site=a.battle.map.sites.find(n=>n.id==='mira');
      if(!site) throw new Error('Mira absente du village');
      if(!press(hero,'#npc-actions button',b=>b.textContent.includes('Accepter'))) {
        const node=hero.window.document.querySelector('[data-site="mira"]');
        if(node && Math.hypot(...site.position.map((n,i)=>n-a.battle.players[state(hero).me].position[i]))<=1.5) node.dispatchEvent(new hero.window.MouseEvent('click',{bubbles:true}));
        else walk(hero,site.position);
      }
    });
    const objective=state(hero).tutorial.hunt_objective;
    const huntZone=objective?.zone || 'lisiere';
    const huntMap=objective?.map || state(hero).tutorial.world.objectives.find(o=>o.zone===huntZone && o.point)?.point || 'hunt';
    const goal=state(hero).tutorial.hunt_goal;
    console.log(`Objectif lu dans le client : ${goal} ennemis, ${state(hero).tutorial.hunt_description}`);
    await runUntil(hero,a=>!a.battle,'Sortie de Rosée',()=>exitTo(hero,null));
    await runUntil(hero,a=>a.field_map===huntMap,'Rejoindre le lieu indiqué par la quête',a=>a.battle?exitTo(hero,huntMap):(travel(hero,huntMap)||travel(hero,huntZone)));
    await runUntil(hero,a=>a.kills>=a.hunt_goal,'Accomplir les objectifs actuels de la quête',a=>{
      if(!a.battle) return travel(hero,huntMap)||travel(hero,huntZone);
      const points=a.battle.map.spawns||[];
      const next=points.find(p=>!(a.battle.explored||[]).some(q=>q.join()===p.join()));
      if(next) walk(hero,next);
      else {
        const destination=a.field_map===huntMap ? huntZone : huntMap;
        if(destination===a.field_map) throw new Error(`Objectif ${a.kills}/${a.hunt_goal}: aucun ennemi restant dans le lieu demandé`);
        exitTo(hero,destination);
      }
    });
    await runUntil(hero,a=>a.field_map===huntZone || !a.battle,'Retour vers la lisière',()=>exitTo(hero,huntZone));
    await runUntil(hero,a=>!a.battle,'Sortie de la lisière',()=>exitTo(hero,null));
    await runUntil(hero,a=>a.field_map==='rosee','Retour à Rosée',()=>travel(hero,'rosee'));
    await runUntil(hero,a=>a.quest==='completed','Valider la quête auprès du PNJ',a=>{
      if(!press(hero,'#npc-actions button',b=>b.textContent.includes('Rendre'))) {
        const site=a.battle.map.sites.find(n=>n.id==='mira');
        const node=hero.window.document.querySelector('[data-site="mira"]');
        if(node && Math.hypot(...site.position.map((n,i)=>n-a.battle.players[state(hero).me].position[i]))<=1.5) node.dispatchEvent(new hero.window.MouseEvent('click',{bubbles:true})); else walk(hero,site.position);
      }
    });
    await runUntil(hero,a=>a.players.every(p=>p.gear.some(g=>g.recipe==='veste')),'Forge : fabriquer et équiper',a=>{
      const site=a.battle.map.sites.find(n=>n.id==='forge');
      walk(hero,site.position);
      for(const c of clients) {
        const card=[...$(c,'forge-catalogue').children].find(n=>n.textContent.includes('Veste'));
        const button=card?.querySelector('button'); if(visible(button)) button.click();
      }
    });
    await runUntil(hero,a=>!a.battle,'Rejoindre le chemin de Brume',()=>exitTo(hero,null));
    await runUntil(hero,a=>a.field_map==='brume' && a.step==='complete','Arrivée à Brume',()=>travel(hero,'brume'),300000);
    assert.deepEqual(errors,[]);
    console.log('DÉMO RÉUSSIE : données réelles, interface uniquement, quête, craft, équipement et Brume.');
  } finally { for(const c of clients) { for(const timer of c.timers) c.window.clearInterval(timer); await wait(()=>c.window.demoIdle(),'fermeture'); c.window.close(); } }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
