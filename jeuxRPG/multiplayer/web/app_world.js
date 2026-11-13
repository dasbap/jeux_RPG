"use strict";
function syncRegionTravel(adventure) {
  const previous = regionTravelState;
  const field = adventure.field_map || null;
  regionTravelState = {session: session.id, field, moving: Boolean(adventure.moving)};
  if (previous?.session === session.id && previous.field && !field && !adventure.moving) {
    currentView = "map";
    document.body.classList.add("hud-menu-open");
    toggleGameMenu(false);
  }
  if (previous?.session === session.id && currentView === "map" &&
      (adventure.moving && !previous.moving || field && previous.field !== field)) {
    document.body.classList.remove("hud-menu-open");
    toggleGameMenu(false);
  }
}
function routeEndpoint(world, route, point) {
  if (point === route.id) return .5;
  if ([route.from,route.from_point,world.zone_entries?.[route.from]].some(id=>id!=null&&id===point)) return 0;
  if ([route.to,route.to_point,world.zone_entries?.[route.to]].some(id=>id!=null&&id===point)) return 1;
  return null;
}
function worldRoutePosition(adventure, route) {
  const transit=adventure.transit;
  if (!transit) return .5;
  const source=routeEndpoint(adventure.world,route,transit.source),target=routeEndpoint(adventure.world,route,transit.destination);
  if (source===null||target===null) return .5;
  const progress=Math.max(0,Math.min(1,adventure.travel_progress ?? 0));
  return source+(target-source)*progress;
}
function journeyRoutePresentation(adventure) {
  const route=adventure.world?.routes?.find(route=>route.id===adventure.position),transit=adventure.transit;
  if (!route||!transit) return null;
  const goal=adventure.journey?.[adventure.journey.length-1] || transit.destination;
  const end=routeEndpoint(adventure.world,route,goal),source=routeEndpoint(adventure.world,route,transit.source),target=routeEndpoint(adventure.world,route,transit.destination);
  if (source===null||target===null||![0,1].includes(end)||end!==(target>source?1:0)) return null;
  const progress=end===1?worldRoutePosition(adventure,route):1-worldRoutePosition(adventure,route);
  const from=adventure.world.places.find(place=>place.id===(end===1?route.from:route.to));
  const to=adventure.world.places.find(place=>place.id===(end===1?route.to:route.from));
  if (!from||!to||!Number.isFinite(route.duration_real_seconds)) return null;
  return {source:from.name,destination:to.name,progress,remaining:Math.max(0,(1-progress)*route.duration_real_seconds)};
}
function renderJourney(adventure) {
  let panel = $("journey-view");
  if (!panel) {
    panel = document.createElement("section");panel.id="journey-view";
    panel.setAttribute("aria-label","Déplacement en cours");
    panel.innerHTML='<strong id="journey-title"></strong><p id="journey-route"></p><div class="journey-track"><span class="journey-start" aria-hidden="true">●</span><span id="journey-player"><svg viewBox="0 0 40 48" aria-hidden="true"><circle cx="20" cy="12" r="7"/><path d="M20 21v13m0-9-10 7m10-7 10 7M20 34l-9 11m9-11 9 11"/></svg><span>Vous</span></span><span class="journey-end" aria-hidden="true">⚑</span></div><progress id="journey-progress" max="1" aria-label="Progression du trajet"></progress><p id="journey-remaining" role="timer"></p>';
    $("battle").append(panel);
  }
  panel.hidden = !adventure.moving || Boolean(adventure.battle);
  if (panel.hidden) return;
  const road=journeyRoutePresentation(adventure);
  const progress = road?.progress ?? adventure.travel_progress ?? 0;
  $("journey-title").textContent="Déplacement en cours";
  $("journey-route").textContent=road?`${road.source} → ${road.destination}`:`${adventure.travel_source_name || adventure.location} → ${adventure.travel_goal_name || adventure.travel_destination_name || "Destination"}`;
  $("journey-player").style.left=`${Math.max(0,Math.min(1,progress))*100}%`;
  $("journey-progress").value=progress;
  $("journey-remaining").textContent=`${Math.ceil(road?.remaining ?? adventure.travel_remaining_real_seconds)} s restantes ${road?"sur ce chemin":"pour cette étape"}`;
}
function worldRouteGroups(routes) {
  const groups = new Map();
  for (const route of routes) {
    const key = [route.from,route.to].sort().join(":");
    if (!groups.has(key)) groups.set(key,{key,routes:[]});
    groups.get(key).routes.push(route);
  }
  return [...groups.values()].map(group => ({...group, name:[...new Set(group.routes.map(route=>route.name.replace(/^Retour\s+(?:(?:[àa·:—-]|vers)\s+)?/i,"").trim()))].join(" / ")}));
}
function worldRouteLabels(groups, places, width, height, measure = text => text.length * 7) {
  const occupied = places.flatMap(place => [
    {x:place.x-20,y:place.y-20,width:40,height:40},
    {x:place.x-measure(place.name || "")/2-6,y:place.y+18,width:measure(place.name || "")+12,height:24},
    {x:place.x-48,y:place.y-38,width:96,height:18},
  ]);
  const overlap = (a,b) => Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y));
  return groups.map(group => {
    const route=group.routes[0],from=places.find(place=>place.id===route.from),to=places.find(place=>place.id===route.to);
    const lines=[];let line="";
    for (const word of group.name.split(/\s+/)) {
      if(line && measure(line+" "+word)>150) {lines.push(line);line="";}
      if(line) line+=" ";
      for(const char of word) {
        if(line && measure(line+char)>150) {lines.push(line);line="";}
        line+=char;
      }
    }
    if(line) lines.push(line);
    const boxWidth=Math.max(30,...lines.map(measure))+16,boxHeight=lines.length*16+10;
    const dx=to.x-from.x,dy=to.y-from.y,length=Math.hypot(dx,dy)||1;
    let best=null;
    for(const fraction of [.5,.35,.65,.2,.8]) for(const side of [-1,1]) for(const gap of [10,28,48]) {
      const offset=(Math.abs(dy/length)*boxWidth+Math.abs(dx/length)*boxHeight)/2+gap;
      const candidate={x:Math.max(6,Math.min(width-boxWidth-6,from.x+dx*fraction-dy/length*offset*side-boxWidth/2)),y:Math.max(6,Math.min(height-boxHeight-6,from.y+dy*fraction+dx/length*offset*side-boxHeight/2)),width:boxWidth,height:boxHeight};
      const score=occupied.reduce((total,box)=>total+overlap(candidate,box),0)*1000+Math.abs(fraction-.5)*length+gap+(side===1?2:0);
      if(!best || score<best.score) best={...candidate,score};
    }
    occupied.push({x:best.x-4,y:best.y-4,width:best.width+8,height:best.height+8});
    return {...best,lines,group};
  });
}
function worldPaths(adventure, destination) {
  destination = adventure.world.zone_entries?.[destination] || destination;
  const graph = adventure.world.graph;
  if (!graph) return null;
  const sources = new Set([adventure.position]);
  if (adventure.transit) { sources.add(adventure.transit.source); sources.add(adventure.transit.destination); }
  return Object.fromEntries([...sources].map(source => {
    const queue = [[source, []]], visited = new Set();
    for (const [node, route] of queue) {
      if (node === destination) return [source, route];
      if (visited.has(node)) continue;
      visited.add(node);
      for (const next of graph[node] || []) if (!visited.has(next)) queue.push([next, [...route, next]]);
    }
    return [source, null];
  }));
}
function renderNarrative(adventure) {
  const story=adventure.narrative, conversation=story?.conversation;
  let dialog=$("story-dialog");
  if(!dialog && story) {
    dialog=document.createElement("dialog");dialog.id="story-dialog";
    dialog.setAttribute("aria-labelledby","story-speaker");
    dialog.innerHTML='<div class="story-heading"><h2 id="story-speaker"></h2><button type="button" id="story-close" class="secondary">Fermer</button></div><p id="story-response" aria-live="polite"></p><div id="story-choices" class="story-choices"></div><h3>Parler de…</h3><div id="story-topics" class="actions"></div><div id="story-service" class="actions"></div><h3 id="story-quest-heading">Quêtes facultatives</h3><div id="story-quests"></div>';
    $("battle").append(dialog);
    const dismiss=()=>{dialog.dataset.dismissed="true";dialog.close();if(!busy)tutorialCommand("story",{npc:dialog.dataset.npc,choice:"close"});};
    $("story-close").onclick=dismiss;
    dialog.addEventListener("cancel",event=>{event.preventDefault();dismiss();});
  }
  if(dialog && !conversation) {if(dialog.open)dialog.close();delete dialog.dataset.dismissed;}
  if(conversation) {
    dialog.dataset.npc=conversation.npc;
    if($("story-speaker").textContent!==conversation.name)$("story-speaker").textContent=conversation.name;
    if($("story-response").textContent!==conversation.text)$("story-response").textContent=conversation.text;
    const send=choice=>tutorialCommand("story",{npc:conversation.npc,choice});
    function buttons(root,entries) {
      const kept=new Set();
      for(const entry of entries) {
        let button=[...root.children].find(node=>node.dataset.storyKey===entry.id);
        if(!button){button=document.createElement("button");button.type="button";button.dataset.storyKey=entry.id;root.append(button);}
        if(button.textContent!==entry.label)button.textContent=entry.label;
        button.disabled=busy || Boolean(entry.disabled);button.onclick=entry.click;kept.add(button);
      }
      for(const node of [...root.children])if(!kept.has(node))node.remove();
    }
    buttons($("story-topics"),conversation.topics.map(topic=>({id:topic.id,label:topic.label,click:()=>send("topic:"+topic.id)})));
    buttons($("story-choices"),conversation.choices.map(choice=>({id:choice.id,label:choice.label+(choice.description?" — "+choice.description:""),click:()=>send("answer:"+choice.id)})));
    buttons($("story-service"),conversation.service==="forge" ? [{id:"forge",label:adventure.forge_unlocked?"Utiliser la forge":"Forge : rendez la quête de Mira pour débloquer l’atelier",disabled:!adventure.forge_unlocked,click:async()=>{dialog.dataset.dismissed="true";dialog.close();await send("close");openForge();}}] : []);
    $("story-quest-heading").hidden=!conversation.quests.length;
    const kept=new Set();
    for(const quest of conversation.quests) {
      let card=[...$("story-quests").children].find(node=>node.dataset.quest===quest.id);
      if(!card){card=document.createElement("article");card.className="story-quest";card.dataset.quest=quest.id;card.append(document.createElement("h4"),document.createElement("p"),document.createElement("p"),document.createElement("div"));$("story-quests").append(card);}
      const [title,description,meta,actions]=card.children;
      if(title.textContent!==quest.name)title.textContent=quest.name;
      if(description.textContent!==quest.description)description.textContent=quest.description;
      const text=`${quest.recommended_level?`Niveau conseillé : ${quest.recommended_level} · `:""}${quest.reward_xp} XP${quest.reward_title?" · Titre : "+quest.reward_title:""}${quest.missing_requirements.length?" · "+quest.missing_requirements.join(" ; "):""}${quest.status==="completed"?" · Terminée":""}`;
      if(meta.textContent!==text)meta.textContent=text;
      const ready=quest.status==="ready",available=quest.status==="available"||quest.status==="completed"&&quest.repeatable;
      buttons(actions,quest.status==="completed"&&!quest.repeatable?[]:[{id:quest.id,label:ready?"Rendre la quête":available?(quest.repeatable&&quest.status==="completed"?"Reprendre ce contrat":"Accepter cette quête"):quest.status==="locked"?"Prérequis à remplir":`En cours : ${quest.progress}/${quest.count}`,disabled:!(ready||available),click:()=>send((ready?"claim:":"accept:")+quest.id)}]);
      kept.add(card);
    }
    for(const card of [...$("story-quests").children])if(!kept.has(card))card.remove();
    if(!dialog.open && !dialog.dataset.dismissed)dialog.showModal();
  }
  let notes=$("story-notes");
  if(!notes && story){notes=document.createElement("details");notes.id="story-notes";const title=document.createElement("summary");title.textContent="Indices et histoire";notes.append(title,document.createElement("div"));$("quest-view").append(notes);}
  if(notes){
    notes.hidden=!story;
    if(story && sectionChanged("story-notes",[session.id,story.notes,story.ending])) {
      const list=notes.lastElementChild;list.replaceChildren();
      for(const note of story.notes){const item=document.createElement("p");const title=document.createElement("strong");title.textContent=note.name+" : ";item.append(title,document.createTextNode(note.description));list.append(item);}
      if(!story.notes.length){const empty=document.createElement("p");empty.textContent="Les témoignages et les inscriptions lus seront conservés ici.";list.append(empty);}
      if(story.ending){const ending=document.createElement("p");ending.textContent=`${story.ending.name} : ${story.ending.text}`;list.append(ending);}
    }
  }
}
function tutorialCommand(action, params = {}) {
  if (["move", "travel"].includes(action) && session?.tutorial) {
    const paths = worldPaths(session.tutorial, params.destination);
    if (paths) params = {...params, paths};
  }
  if (session) return command(action, {session_id: session.id, revision: session.revision, ...(["battle_move", "stop_move", "unit_order", "strike", "skill", "hide", "harvest", "control_units", "unit_skill", "leave_battle"].includes(action) ? {encounter: session.tutorial.encounter_number} : {}), ...(["move", "travel", "explore", "talk"].includes(action) && session.tutorial.world_context ? {world_context: session.tutorial.world_context} : {}), ...params});
}
function paragraphs(container, texts) {
  $(container).replaceChildren();
  for (const text of texts) {
    const p = document.createElement("p");
    p.textContent = text;
    $(container).append(p);
  }
}
function mountWorldMap(source, container = $("world-map")) {
  source.dataset.mapBounds = source.getAttribute("viewBox");
  const retained = [...container.children].find(node => node.dataset.map === source.dataset.map);
  if (!retained) { container.append(source); installWorldCamera(source); return source; }
  function update(target, fresh) {
    for (const attr of [...target.attributes]) target.removeAttribute(attr.name);
    for (const attr of fresh.attributes) target.setAttribute(attr.name, attr.value);
    target.onclick = fresh.onclick; target.ondblclick = fresh.ondblclick; target.onkeydown = fresh.onkeydown;
    if (!fresh.children.length) { target.textContent = fresh.textContent; return; }
    const old = [...target.children];
    const kept = [...fresh.children].map((child, index) => {
      const destination = child.dataset.destination, point = child.dataset.point;
      const existing = destination ? old.find(node => node.dataset.destination === destination) : point ? old.find(node => node.dataset.point === point) : old[index]?.tagName === child.tagName && !old[index].dataset.destination && !old[index].dataset.point ? old[index] : null;
      if (existing) { update(existing, child); return existing; }
      return child;
    });
    for (const child of old) if (!kept.includes(child)) child.remove();
    for (const child of kept) if (child.parentElement !== target) target.append(child);
  }
  update(retained, source);
  installWorldCamera(retained);
  return retained;
}
function activeHudQuest(adventure) {
  const quests = adventure.quest_journal || [];
  return quests.find(quest => quest.id === trackedQuestId && ["active","ready"].includes(quest.status)) || quests.find(quest => ["active","ready"].includes(quest.status));
}
function questDestination(adventure, quest) {
  const ready = quest.progress >= quest.count;
  const step = quest.steps?.find(step=>!step.done);
  const destination = ready || ["craft","upgrade"].includes(quest.kind) ? quest.npc : step?.npc || quest.map || quest.zone;
  const place = adventure.world.places.find(place => place.id === destination || place.points?.some(point => point.id === destination));
  return {zone: place?.id || quest.zone || adventure.world.current, point: ready ? quest.npc : step?.npc || quest.map || (place?.id !== destination ? destination : null), label: ready ? `À rendre : ${quest.name}` : `${quest.name} · ${quest.progress}/${quest.count}`};
}
function hudQuestTarget(adventure) {
  const active = activeHudQuest(adventure);
  if (active) {
    return questDestination(adventure, active);
  }
  const contract = (adventure.endgame || []).find(item => item.status === "claimable") || (adventure.endgame || []).find(item => item.status === "active");
  if (contract) return {zone: contract.zone || adventure.world.current, point: null, label: `${contract.name} · ${contract.progress}/${contract.count}`};
  return {zone: adventure.world.current, point: null, label: adventure.objective || "Explorer"};
}
function localMapPositions(place) {
  const entry = place.entry || [70, 110];
  const positions = new Map([[place.id, {x: entry[0], y: entry[1]}]]);
  const preferred = place.points.map((point, index) => ({id: point.id, x: point.x ?? (index % 2 ? 450 : 270), y: point.y ?? 65 + Math.floor(index / 2) * 110}));
  const overlaps = (point, others) => [...others].some(other => Math.abs(point.x - other.x) < 80 && Math.abs(point.y - other.y) < 42);
  for (const point of preferred) {
    let position = {x: point.x, y: point.y};
    let attempt = 0;
    while (overlaps(position, positions.values())) {
      do {
        position = {x: point.x + attempt % 3 * 180, y: point.y + (Math.floor(attempt / 3) + 1) * 90};
        attempt++;
      } while (overlaps(position, preferred));
    }
    positions.set(point.id, position);
  }
  return positions;
}
function renderHudNavigation(adventure) {
  const svg = $("hud-minimap");
  if (!svg) return;
  const ns = "http://www.w3.org/2000/svg", target = hudQuestTarget(adventure), battle = adventure.battle, map = battle?.map;
  $("hud-objective").textContent = target.label;
  $("hud-objective").title = target.label;
  $("minimap-location").textContent = map?.name || adventure.location;
  $("minimap-location").title = map?.name || adventure.location;
  svg.toggleAttribute("hidden", !map);
  $("minimap-exits").hidden = !map;
  $("minimap-world").hidden = Boolean(map);
  $("minimap-toggle").disabled = !map;
  $("hud-navigation").querySelector(".minimap-legend").hidden = !map;
  if (!map) return;
  const element = (tag, attrs = {}, text = "") => {
    const node = document.createElementNS(ns, tag);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    if (text) node.textContent = text;
    return node;
  };
  svg.setAttribute("viewBox", `-2 -2 ${map.width + 4} ${map.height + 4}`);
  svg.setAttribute("aria-label", `Carte de ${map.name}. Votre position, le terrain découvert et les sorties.`);
  const explored = adventure.field_map ? new Set((battle.explored || []).map(point => point.join(","))) : null;
  const discovered = point => !explored || explored.has(point.join(","));
  if (sectionChanged("minimap-terrain", [session.id, map.id, map.terrain_version, map.width, map.height, map.paths, map.water, map.bridges, map.cover, map.blocked, map.decorations, battle.explored])) {
    svg.replaceChildren();
    svg.append(element("rect", {x:0,y:0,width:map.width,height:map.height,class:"mini-fog"}));
    const sets = Object.fromEntries(["paths", "water", "bridges", "cover", "blocked"].map(key => [key, new Set((map[key] || []).map(point => point.join(",")))]));
    const buildings = new Set((map.decorations || []).filter(item=>["house","camp"].includes(item.kind)).map(item=>item.position.join(",")));
    const paths = {};
    for (let y = 0; y < map.height; y++) for (let x = 0; x < map.width; x++) {
      if (!discovered([x,y])) continue;
      const key = `${x},${y}`;
      const kind = sets.bridges.has(key) ? "bridge" : sets.water.has(key) ? "water" : buildings.has(key) ? "building" : sets.cover.has(key) || sets.blocked.has(key) ? "wall" : sets.paths.has(key) ? "road" : "ground";
      paths[kind] = (paths[kind] || "") + `M${x} ${y}h1v1h-1z`;
    }
    for (const [kind, d] of Object.entries(paths)) svg.append(element("path", {d,class:`mini-terrain mini-${kind}`}));
    svg.append(element("g", {"data-mini-overlay":"true"}));
  }
  const overlay = svg.querySelector("[data-mini-overlay]");
  overlay.replaceChildren();
  const radius = Math.max(map.width, map.height) / 65;
  function mark(point, kind, label, id, glyph = "") {
    const [x,y] = point.map(value => value + .5);
    const markerRadius = kind === "exit" ? radius*2.2 : radius;
    const node = element("g", {class:`mini-marker mini-${kind}`, "data-mini-point":id});
    node.append(element("title", {}, label));
    node.append(kind === "exit" ? element("rect", {x:x-markerRadius,y:y-markerRadius,width:markerRadius*2,height:markerRadius*2,rx:markerRadius*.2}) : element("circle", {cx:x,cy:y,r:markerRadius}));
    if (glyph) node.append(element("text", {x,y:y+markerRadius*.4,"font-size":markerRadius*1.5,"text-anchor":"middle"},glyph));
    overlay.append(node);
    return node;
  }
  const quest = activeHudQuest(adventure), ready = quest && quest.progress >= quest.count;
  const questHere = quest && (!quest.map || quest.map === adventure.field_map) && (!quest.zone || [adventure.world.current,adventure.field_map,adventure.position].includes(quest.zone));
  const objective = node => {node.classList.add("mini-objective");node.dataset.miniObjective="true";};
  for (const site of map.sites || []) if (discovered(site.position)) {
    const node=mark(site.position,"site",site.name,site.id);
    if (ready && site.id === quest.npc) objective(node);
  }
  for (const mob of adventure.mobs || []) if (mob.stats.hp.current > 0) {
    const node=mark(mob.position,"enemy",mob.name,mob.combat_id);
    if (questHere && !ready && quest.kind === "kill" && quest.target === mob.mob_id) objective(node);
  }
  for (const [index, exit] of (map.exits || []).entries()) mark(exit.position,"exit",exit.name,`exit-${index}`,String(index+1));
  const actor = battle.players[session.me];
  if (actor) {
    const [x,y] = actor.position.map(value => value+.5);
    const player = element("path", {d:`M${x} ${y-radius*2.3}l${radius*1.5} ${radius*3.5}l${-radius*1.5} ${-radius*.7}l${-radius*1.5} ${radius*.7}z`,class:"mini-player", "data-mini-point":"player"});
    player.append(element("title", {}, "Vous êtes ici"));overlay.append(player);
  }
  const view = $("world-map").querySelector(".battle-map")?.getAttribute("viewBox")?.split(/\s+/).map(Number);
  if (view?.length === 4) overlay.append(element("rect", {x:view[0]/40,y:view[1]/40,width:view[2]/40,height:view[3]/40,class:"mini-viewport"}));
  if (sectionChanged("minimap-exits", [session.id, map.id, map.exits])) {
    $("minimap-exits").replaceChildren();
    for (const [index, exit] of (map.exits || []).entries()) {
      const button = document.createElement("button");
      button.type = "button";button.textContent = `${index+1} · ${exit.name}`;button.title = `Repérer : ${exit.name}`;
      button.onclick = () => focusMinimapPoint(exit.position);
      $("minimap-exits").append(button);
    }
  }
  svg.onclick = event => {
    const matrix = svg.getScreenCTM?.();
    if (!matrix) return;
    const point = svg.createSVGPoint();point.x = event.clientX;point.y = event.clientY;
    const cell = point.matrixTransform(matrix.inverse());
    if (cell.x >= 0 && cell.y >= 0 && cell.x < map.width && cell.y < map.height) focusMinimapPoint([cell.x,cell.y]);
  };
  svg.onkeydown = event => {if (["Enter"," "].includes(event.key)) {event.preventDefault();returnCameraToPlayer();}};
}
function focusMinimapPoint(point) {
  const adventure = session?.tutorial;
  if (!adventure?.battle || !fieldCamera) return;
  clearTimeout(cameraReturnTimer);
  fieldCamera.follow = false;[fieldCamera.x,fieldCamera.y] = point;
  renderGame(adventure);
  cameraReturnTimer = setTimeout(returnCameraToPlayer, 5000);
}
function questJournalType(quest) {
  return quest.quest_type || (["main", "side", "tutorial"].includes(quest.category) ? quest.category : "side");
}
function matchesQuestType(quest, type) {
  return !type || (type === "repeatable" ? Boolean(quest.repeatable) : questJournalType(quest) === type);
}
function renderQuestJournal(adventure) {
  const quests = adventure.quest_journal || [], active = activeHudQuest(adventure);
  const categories = {hunt:"Chasse",boss:"Créature d’élite",crafting:"Artisanat",upgrade:"Perfectionnement",standard:"Contrat",main:"Aventure",side:"Contrat",tutorial:"Découverte",investigation:"Enquête",exploration:"Exploration",service:"Service",encounter:"Rencontre",dialogue:"Dialogue"};
  const types = {main:"Principale",side:"Secondaire",tutorial:"Découverte"};
  let filters = $("quest-filters");
  if (!filters) {
    filters=document.createElement("div");filters.id="quest-filters";
    for (const [id,title,options] of [
      ["quest-category","Catégorie",[["","Toutes"],...Object.entries(categories)]],
      ["quest-type","Type de quête",[["","Tous"],["main","Principales"],["side","Secondaires"],["repeatable","Répétables"],["tutorial","Découverte"]]],
    ]) {
      const label=document.createElement("label");label.className="quest-filter";label.textContent=title;
      const select=document.createElement("select");select.id=id;
      for (const [value,name] of options) {const option=document.createElement("option");option.value=value;option.textContent=name;select.append(option);}
      select.onchange=()=>renderGame(session.tutorial);label.append(select);filters.append(label);
    }
    $("quest-description").after(filters);
  }
  const filter=$("quest-category"),typeFilter=$("quest-type");
  let list = $("quest-list");
  if (!list) {list=document.createElement("div");list.id="quest-list";filters.after(list);}
  for (const option of filter.options) {
    const hidden = Boolean(option.value && !quests.some(quest=>quest.category===option.value));
    if(option.hidden !== hidden) option.hidden = hidden;
  }
  if (filter.selectedOptions[0]?.hidden) filter.value="";
  $("quest-progress").hidden = true;$("quest-description").hidden = true;
  const matches=quest=>Boolean(quest)&&(!filter.value||quest.category===filter.value)&&matchesQuestType(quest,typeFilter.value);
  $("quest-actions").hidden = !matches(active);
  if (!sectionChanged("quest-cards", [session.id, quests, active?.id,filter.value,typeFilter.value,adventure.players?.map(player=>player.gear)])) return;
  list.replaceChildren();
  const visible = quests.filter(matches);
  if (!visible.length) {const text=document.createElement("p");text.textContent=quests.length?"Aucune quête ne correspond à ces filtres.":"Aucune quête acceptée. Les habitants proposent des contrats facultatifs.";list.append(text);}
  for (const quest of visible) {
    const card=document.createElement("article");card.className="quest-card";card.dataset.quest=quest.id;
    card.classList.toggle("tracked",quest.id===active?.id);
    const ready=quest.progress>=quest.count, completed=quest.status==="completed", locked=quest.status==="locked";
    const heading=document.createElement("h4");heading.textContent=quest.name;
    const header=document.createElement("div");header.className="quest-heading";header.append(heading);
    const status=document.createElement("span");status.className="quest-status";status.textContent=`${categories[quest.category] || "Contrat"} · ${types[questJournalType(quest)] || "Secondaire"}${quest.repeatable?" · Répétable":""} · Facultative · ${completed?"Terminée":locked?"Prérequis à remplir":ready?"À rendre":"En cours"}`;
    const description=document.createElement("p");description.textContent=quest.description;
    if (quest.id===adventure.forge_unlock_quest?.id && !/forge (?:du village )?de Rosée/i.test(description.textContent)) description.textContent+=" Récompense d’accès : forge du village de Rosée.";
    if(quest.requirements?.quests?.length)description.textContent+=` Suite de : ${quest.requirements.quests.map(id=>quests.find(previous=>previous.id===id)?.name || id).join(", ")}.`;
    if(locked)description.textContent+=` ${quest.missing_requirements.join(" ; ")}.`;
    const gearLevel=Math.max(0,...(adventure.players || []).flatMap(player=>(player.gear || []).filter(piece=>piece.recipe===quest.target).map(piece=>piece.level)));
    const progress=document.createElement("progress");progress.max=quest.kind==="upgrade"?quest.upgrade_level || 1:quest.count;progress.value=quest.kind==="upgrade"?(ready?progress.max:gearLevel):quest.progress;progress.setAttribute("aria-label",`Progression : ${quest.name}`);
    const details=document.createElement("p");details.className="quest-meta";details.textContent=`${quest.kind==="upgrade"?`Équipement +${ready?quest.upgrade_level || 1:gearLevel} / +${quest.upgrade_level || 1} requis`:`${quest.progress}/${quest.count}`} · ${quest.reward_xp} XP${ready&&!completed&&!locked?" · Retournez voir le donneur de quête":""}`;
    const progressRow=document.createElement("div");progressRow.className="quest-progress-row";progressRow.append(progress,details);
    card.append(header,status,description,progressRow);
    if(quest.steps?.length) {
      const steps=document.createElement("ul");steps.className="quest-steps";
      for(const step of quest.steps) {const row=document.createElement("li");row.textContent=`${step.done?"✓":"○"} ${step.name}`;steps.append(row);}
      card.append(steps);
    }
    if (!completed && !locked) {
      const follow=document.createElement("button");follow.type="button";follow.dataset.trackQuest=quest.id;follow.textContent=quest.id===active?.id?"Suivie":"Suivre";follow.setAttribute("aria-label",`Suivre cette quête : ${quest.name}`);follow.setAttribute("aria-pressed",String(quest.id===active?.id));
      follow.onclick=()=>{trackedQuestId=quest.id;renderGame(session.tutorial);};header.append(follow);
    }
    list.append(card);
  }
}
function equipmentBonuses(piece) {
  return [["hp", "PV"], ["endurance", "endurance"], ["force", "force"], ["intelligence", "intelligence"], ["sagesse", "sagesse"]].filter(([key]) => piece[key] > 0).map(([key, label]) => `+${piece[key]} ${label}`).join(" · ");
}
function renderWorld(adventure, me, mapContainer = $("world-map"), {overview = true} = {}) {
  paragraphs("equipment-details", me.gear.length ? me.gear.map(p => `${p.name} +${p.level} · ${equipmentBonuses(p)}`) : ["Aucun équipement équipé. Les recettes disponibles sont proposées à la forge."]);
  let setPanel=$("equipment-set-details");
  if(!setPanel){setPanel=document.createElement("div");setPanel.id="equipment-set-details";$("equipment-details").after(setPanel);}
  setPanel.replaceChildren();
  for(const set of me.equipment_sets || []) {
    const card=document.createElement("article");card.className="codex-card equipment-set";card.dataset.set=set.id;
    const title=document.createElement("h4");title.textContent=`${set.name} · ${set.pieces} pièce(s) équipée(s)`;card.append(title);
    for(const tier of set.tiers) {
      const row=document.createElement("p");row.className="set-tier";row.classList.toggle("active",tier.active);row.dataset.pieces=tier.pieces;
      row.textContent=`${tier.pieces} pièces · ${tier.active?"Actif":"Inactif"} · ${equipmentBonuses(tier.bonuses)}`;card.append(row);
    }
    const total=document.createElement("p");total.className="set-total";total.textContent=`Bonus cumulés : ${equipmentBonuses(set.bonuses) || "aucun palier actif"}`;card.append(total);
    setPanel.append(card);
  }
  const items = Object.entries(me.inventory).filter(([, quantity]) => quantity > 0);
  paragraphs("inventory-details", items.length ? items.map(([item, quantity]) => `${quantity} ${adventure.material_names?.[item] || item} · matériau pour la forge`) : ["Votre inventaire est vide."]);
  $("gold-balance").textContent = `Or : ${me.gold ?? 0}`;
  $("market-panel").hidden = !adventure.merchant;
  $("market-details").replaceChildren();
  if (adventure.merchant) {
    $("market-title").textContent = `Commerce · ${adventure.merchant.name}`;
    for (const price of me.market || []) {
      const row = document.createElement("article"); row.className = "codex-card";
      const title = document.createElement("strong"); title.textContent = price.name; row.append(title);
      const info = document.createElement("span"); info.textContent = ` · achat ${price.buy} or · vente ${price.sell} or`; row.append(info);
      const buy = document.createElement("button"); buy.textContent = "Acheter 1"; buy.disabled = busy || (me.gold ?? 0) < price.buy; buy.onclick = () => tutorialCommand("buy", {npc: adventure.merchant.id, item: price.id, quantity: 1}); row.append(buy);
      const sell = document.createElement("button"); sell.textContent = "Vendre 1"; sell.disabled = busy || (me.inventory[price.id] || 0) < 1; sell.onclick = () => tutorialCommand("sell", {npc: adventure.merchant.id, item: price.id, quantity: 1}); row.append(sell);
      $("market-details").append(row);
    }
  }
  const places = adventure.world.places;
  const visiblePlaces = new Set(places.map(place => place.id));
  const world = {...adventure.world, routes: adventure.world.routes.filter(route => visiblePlaces.has(route.from) && visiblePlaces.has(route.to))};
  const locked = busy || Boolean(adventure.battle && (!adventure.field_map || adventure.battle.hostiles_alive));
  function keepMapOpen() {
    currentView = "map";
    document.body.classList.add("hud-menu-open");
    if (session?.tutorial) renderGame(session.tutorial);
  }
  function choosePoint(point) {
    mapPoint = point.id;
    if (point.locked_reason) message(point.locked_reason);
    keepMapOpen();
  }
  function visitPoint(point) {
    if (locked) return;
    if (point.id === "leon" && point.can_interact) return tutorialCommand("talk", {npc: "leon"});
    if (adventure.position !== point.id || adventure.moving) return requestTravel(point.id);
    if (point.locked_reason) return message(point.locked_reason);
    if (point.action === "explore") return tutorialCommand("explore");
    choosePoint(point);
  }
  if (!places.some(p => p.id === mapPlace)) mapPlace = places.find(p => p.id === world.current)?.id || places[0]?.id;
  const place = places.find(p => p.id === mapPlace);
  syncSelectOptions($("map-place"), places.map(p => [p.id, `${p.name} · ${p.visited ? "visité" : "non visité"}`]), mapPlace);
  const namespace = "http://www.w3.org/2000/svg";
  function svgElement(tag, attrs = {}, text = "") {
    const element = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    if (text) element.textContent = text;
    return element;
  }
  const generalWidth = Math.max(610, ...places.map(p => p.x + 130)), generalHeight = Math.max(260, ...places.map(p => p.y + 70));
  const svg = svgElement("svg", {viewBox: `0 0 ${generalWidth} ${generalHeight}`, role: "group", "aria-label": "Carte des lieux et chemins découverts", class: "zone-map"});
  const routeGroups = worldRouteGroups(world.routes);
  const drawnRoutes = new Set();
  for (const route of world.routes) {
    const from = places.find(p => p.id === route.from);
    const to = places.find(p => p.id === route.to);
    const group = routeGroups.find(group=>group.routes.includes(route));
    if (!drawnRoutes.has(group.key)) {
      drawnRoutes.add(group.key);
      svg.append(svgElement("line", {x1: from.x, y1: from.y, x2: to.x, y2: to.y, class: route.destination ? "known-route accessible-route" : "known-route"}));
    }
    if (adventure.position === route.id) {
      const proportion = worldRoutePosition(adventure,route);
      const x = from.x + (to.x - from.x) * proportion;
      const y = from.y + (to.y - from.y) * proportion;
      svg.append(svgElement("circle", {cx: x, cy: y, r: 8, class: "visited-node world-traveller", "data-route":route.id}));
      svg.append(svgElement("text", {x, y: y - 20, class: "place-label"}, "Vous êtes ici"));
    }
  }
  const context = typeof CanvasRenderingContext2D !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
  if(context) context.font="600 12px system-ui";
  for(const label of worldRouteLabels(routeGroups,places,generalWidth,generalHeight,context ? text=>context.measureText(text).width : undefined)) {
    const group=svgElement("g",{class:"route-name","aria-label":label.group.name});
    const text=svgElement("text",{"text-anchor":"middle"});
    label.lines.forEach((line,index)=>text.append(svgElement("tspan",{x:label.x+label.width/2,y:label.y+17+index*16},line)));
    group.append(svgElement("rect",{x:label.x,y:label.y,width:label.width,height:label.height,rx:6}),text,svgElement("title",{},label.group.name));
    svg.append(group);
  }
  for (const p of places) {
    const group = svgElement("g", {role: "button", tabindex: "0", "aria-label": `${p.name}, ${p.visited ? "visité" : "non visité"}`, "aria-pressed": String(p.id === mapPlace), class: "map-node", "data-destination": p.id});
    group.append(svgElement("circle", {cx: p.x, cy: p.y, r: p.id === world.current ? 15 : 11, class: p.visited ? "visited-node" : "unknown-node"}));
    group.append(svgElement("text", {x: p.x, y: p.y + 29, class: "place-label"}, p.name));
    if (p.id === world.current && !world.routes.some(r => r.id === adventure.position)) group.append(svgElement("text", {x: p.x, y: p.y - 24, class: "place-label"}, "Vous êtes ici"));
    const choose = () => { mapPlace = p.id; mapPoint = ""; keepMapOpen(); };
    group.onclick = choose;
    group.ondblclick = () => requestTravel(p.id);
    group.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); requestTravel(p.id); } };
    svg.append(group);
  }
  for (const member of socialState?.team?.members || []) {
    if (!member.online || member.player_id === me.id) continue;
    const place = places.find(point => point.id === member.zone);
    if (!place) continue;
    const group = svgElement("g", {class: "world-player world-ally", "data-ally": member.player_id});
    group.append(svgElement("circle", {cx: place.x + 24, cy: place.y - 12, r: 8}));
    group.append(svgElement("text", {x: place.x + 24, y: place.y - 28, class: "place-label"}, member.name));
    group.append(svgElement("title", {}, `${member.name} · ${member.location} · serveur ${member.realm}`));
    svg.append(group);
  }
  if (mapMarker) {
    const marker = world.objectives.find(m => m.zone === mapMarker.zone && m.point === mapMarker.point);
    if (marker) svg.append(svgElement("circle", {cx: marker.x, cy: marker.y, r: 24, class: "objective-ring", "aria-label": "Objectif à découvrir ou rejoindre"}));
  }
  svg.dataset.map = "general";
  const worldMapNodes = overview ? [mountWorldMap(svg, mapContainer)] : [];
  if (place.points.length) {
    const entry = place.entry || [70, 110];
    const positions = localMapPositions(place);
    const localPoints = [...positions.values()];
    const localLeft = Math.min(0,...localPoints.map(point=>point.x-150)), localTop = Math.min(0,...localPoints.map(point=>point.y-45));
    const localRight = Math.max(610,...localPoints.map(point=>point.x+150)), localBottom = Math.max(220,...localPoints.map(point=>point.y+70));
    const local = svgElement("svg", {viewBox: `${localLeft} ${localTop} ${localRight-localLeft} ${localBottom-localTop}`, role: "group", "aria-label": `Points de ${place.name}`, class: "zone-map"});
    local.append(svgElement("text", {x: (localLeft+localRight) / 2, y: localTop+20, class: "place-label"}, `Points de ${place.name}`));
    local.append(svgElement("circle", {cx: entry[0], cy: entry[1], r: 10, class: "visited-node"}));
    local.append(svgElement("text", {x: entry[0], y: entry[1] + 28, class: "place-label"}, "Entrée"));
    if (adventure.position === place.id) local.append(svgElement("text", {x: entry[0], y: entry[1] - 25, class: "place-label"}, "Vous êtes ici"));
    for (const [source, position] of positions) for (const destination of world.graph[source] || []) {
      const endpoint = positions.get(destination);
      if (endpoint && source < destination) local.append(svgElement("line", {x1: position.x, y1: position.y, x2: endpoint.x, y2: endpoint.y, class: "known-route"}));
    }
    place.points.forEach(point => {
      const {x, y} = positions.get(point.id);
      const node = svgElement("g", {role: "button", tabindex: "0", "aria-label": point.name, "aria-disabled": String(locked), "data-point": point.id, class: "map-node"});
      node.append(svgElement("circle", {cx: x, cy: y, r: adventure.position === point.id ? 15 : 10, class: "visited-node"}));
      const icons = {pnj: "●", atelier: "⚒", rencontre: "⚔", repère: "◆"};
      node.append(svgElement("text", {x, y: y + 4, class: "point-icon"}, icons[point.type] || "◆"));
      node.append(svgElement("text", {x, y: y + 25, class: "place-label"}, point.name));
      if (mapMarker?.zone === place.id && mapMarker.point === point.id) node.append(svgElement("circle", {cx: x, cy: y, r: 23, class: "objective-ring"}));
      if (adventure.position === point.id) node.append(svgElement("text", {x, y: y - 25, class: "place-label"}, "Vous êtes ici"));
      const choose = () => choosePoint(point);
      node.onclick = choose;
      node.ondblclick = () => visitPoint(point);
      node.onkeydown = event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); visitPoint(point); } };
      local.append(node);
    });
    local.dataset.map = `detail:${place.id}`;
    worldMapNodes.push(mountWorldMap(local, mapContainer));
  }
  for (const child of [...mapContainer.children]) if (!worldMapNodes.includes(child)) child.remove();
  paragraphs("place-details", [`${place.name} · ${place.type} · ${place.id === world.current ? "vous êtes ici" : place.visited ? "déjà visité" : "encore non visité"}`, place.description]);
  $("map-routes").replaceChildren();
  for (const route of world.routes.filter(r => r.from === place.id || r.to === place.id)) {
    const p = document.createElement("p");
    const duration = route.kind === "passage" ? "Passage immédiat" : `${(route.duration_real_seconds ?? route.distance_km / 6 * 3600 / 3).toFixed(1)} s réelles de trajet`;
    p.textContent = `${route.name} · ${duration} : ${route.from_map_name || places.find(p => p.id === route.from).name} ${route.bidirectional === false ? "→" : "↔"} ${route.to_map_name || places.find(p => p.id === route.to).name}`;
    $("map-routes").append(p);

  }
  $("map-points").replaceChildren();
  $("point-actions").replaceChildren();
  for (const point of place.points) {
    const button = document.createElement("button");
    button.textContent = point.name;
    button.className = "secondary";
    button.setAttribute("aria-pressed", String(point.id === mapPoint));
    button.addEventListener("click", () => choosePoint(point));
    $("map-points").append(button);
  }
  const point = place.points.find(p => p.id === mapPoint);
  paragraphs("point-details", point ? [`${point.name} · ${point.type}${adventure.position === point.id ? " · Vous êtes ici" : ""}`, point.description, point.locked_reason || (point.action ? "Une interaction est disponible ici." : adventure.mob ? "Terminez le combat pour interagir avec les lieux." : "Aucune interaction disponible à cette étape.")] : [place.points.length ? "Sélectionnez un point pour consulter ses détails et interactions." : "Les points de ce lieu seront révélés lors de votre visite."]);
  if (!locked && point && (adventure.position !== point.id || adventure.moving) && point.id !== "leon") {
    const move = document.createElement("button");
    move.textContent = "Se déplacer à ce point";
    move.disabled = busy;
    move.addEventListener("click", () => requestTravel(point.id, point.name, place.id));
    $("point-actions").append(move);
  }
  if (!locked && (place.id !== world.current || adventure.moving) && !world.routes.some(route => route.destination === place.id)) {
    const move = document.createElement("button");
    move.textContent = `Rejoindre ${place.name}`;
    move.disabled = busy;
    move.addEventListener("click", () => requestTravel(place.id, place.name, place.id));
    $("map-routes").append(move);
  }
  const nearbyPoint = point && (adventure.field_interactions || []).find(site => site.id === point.id);
  if (!locked && nearbyPoint?.dialogue) {
    const talk = document.createElement("button");
    talk.textContent = `Parler à ${nearbyPoint.name}`;
    talk.disabled = busy;
    talk.addEventListener("click", () => tutorialCommand("talk", {npc: nearbyPoint.id}));
    $("point-actions").append(talk);
  }
  if (!locked && point?.action) {
    const button = document.createElement("button");
    button.textContent = point.action === "explore" ? "Explorer ce point" : point.action === "dialogue" ? "Parler" : "Ouvrir la forge";
    button.disabled = busy;
    button.addEventListener("click", () => point.action === "explore" ? tutorialCommand("explore") : point.action === "dialogue" ? tutorialCommand("talk", {npc: point.id}) : showView("craft"));
    $("point-actions").append(button);
  }
  $("bestiary-details").replaceChildren();
  if (!world.bestiary.length) paragraphs("bestiary-details", ["Aucun monstre rencontré. Le bestiaire se complète à chaque découverte."]);
  const damageTypes = {PHYSICAL: "physique", MAGIC: "magique", SACRED: "sacré"};
  const selectedMap = $("bestiary-map").value;
  const maps = [...new Map(world.bestiary.flatMap(m => m.spawn_maps || []).map(m => [m.id, m])).values()];
  syncSelectOptions($("bestiary-map"), [["", "Toutes les cartes découvertes"], ...maps.map(map => [map.id, map.name])], selectedMap);
  $("bestiary-sort-label").hidden = maps.length < 2;
  const query = $("bestiary-search").value.trim().toLocaleLowerCase();
  const filtered = world.bestiary.filter(m => (!$("bestiary-map").value || m.spawn_maps.some(p => p.id === $("bestiary-map").value)) && `${m.name} ${m.loot.map(p => p.item).join(" ")} ${(m.rare_loot || []).map(p => p.item).join(" ")}`.toLocaleLowerCase().includes(query));
  if (world.bestiary.length && !filtered.length) paragraphs("bestiary-details", ["Aucun mob découvert ne correspond à ces filtres."]);
  for (const mob of filtered) {
    const card = document.createElement("article");
    card.className = "codex-card";
    const title = document.createElement("h4");
    title.textContent = `${mob.name} · rang ${mob.rank}`;
    card.append(title);
    for (const text of [mob.description,
      `PV : ${mob.hp.first_encounter} au premier combat, ${mob.hp.hunt} en chasse ou entraînement.`,
      `Force ${mob.stats.force} · Endurance ${mob.stats.endurance} · Intelligence ${mob.stats.intelligence} · Sagesse ${mob.stats.sagesse}`,
      `Faiblesses : ${mob.weaknesses.map(t => damageTypes[t] || t).join(", ") || "aucune"}`,
      `Résistances : ${mob.resistances.map(t => damageTypes[t] || t).join(", ") || "aucune"}`,
      `Matériaux donnés par victoire : ${mob.loot.map(item => `${item.quantity === item.max_quantity ? item.quantity : `${item.quantity}–${item.max_quantity}`} ${item.item} (${(100 * item.chance).toFixed(1)} %, ${item.attempts} tirage(s))`).join(", ")}`,
      `Expérience de référence au niveau 1 : ${mob.xp.hunt} XP. Varie selon le niveau du mob et du joueur qui porte le dernier coup. Entraînement : aucun butin ni XP.`,
      `Cartes de spawn découvertes : ${[...(mob.spawn_maps || [])].sort((a, b) => a.name.localeCompare(b.name) * ($("bestiary-sort").value === "desc" ? -1 : 1)).map(p => p.name).join(", ")}`,
      `Matériaux rares au dépeçage : ${(mob.rare_loot || []).map(p => `${p.item} (${(100 * p.chance).toFixed(1)} %, ${p.attempts} tirage(s), ${p.min}–${p.max} par réussite)`).join(", ")}`, `Capacités : ${(mob.abilities || []).map(a => `${a.name} (niveau ${a.level})`).join(", ") || "attaque classique"}`, mob.materials_usage]) {
      const p = document.createElement("p");
      p.textContent = text;
      card.append(p);
    }
    $("bestiary-details").append(card);
  }
}
function toggleGameMenu(open = $("game-menu-items").hidden) {
  $("game-menu-items").hidden = !open;
  $("game-menu-toggle").setAttribute("aria-expanded", String(open));
  document.body.classList.toggle("gear-menu-open",open);
}
function openForge() {
  if (!session?.tutorial) return;
  renderGame(session.tutorial);
  $("forge-feedback").textContent = "";
  if (!$("craft-view").open) $("craft-view").showModal();
}
function showView(view, {toggle = true} = {}) {
  if (view === "craft") return tutorialCommand("talk", {npc: "forge"});
  toggleGameMenu(false);
  if (toggle && currentView === view && document.body.classList.contains("hud-menu-open")) {document.body.classList.remove("hud-menu-open");currentView = "map";if(session?.tutorial) renderGame(session.tutorial);return;}
  if (["social", "options", "stats", "equipment", "inventory", "quest", "map", "bestiary", "achievements"].includes(view)) currentView = view;
  document.body.classList.toggle("hud-menu-open", Boolean(session?.tutorial));
  renderSocial();
  if (session && session.tutorial) renderGame(session.tutorial);
}

function renderEndgame(adventure) {
  const contracts = adventure.endgame || [];
  $("endgame-contracts").hidden = !contracts.length;
  if (!sectionChanged("endgame", [session.id, contracts, busy, Boolean(adventure.battle), Boolean(adventure.transit)])) return;
  $("endgame-list").replaceChildren();
  for (const contract of contracts) {
    const row = document.createElement("article");
    row.dataset.endgameId = contract.id;
    const description = document.createElement("p");
    const status = {locked: `Verrouillé · tutoriel terminé et niveau ${contract.min_level} requis`, active: "En cours", claimable: "Récompense disponible", completed: "Accompli"}[contract.status];
    description.textContent = `${contract.name} · ${contract.progress}/${contract.count} · ${contract.reward_xp} XP · ${contract.repeatable ? "Répétable" : "Unique"} · ${status}`;
    row.append(description);
    if (contract.status === "claimable") {
      const claim = document.createElement("button");
      claim.textContent = "Recevoir la récompense";
      claim.disabled = busy || Boolean(adventure.battle) || Boolean(adventure.transit);
      claim.onclick = () => tutorialCommand("endgame_claim", {challenge: contract.id});
      row.append(claim);
    }
    $("endgame-list").append(row);
  }
}
