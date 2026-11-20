"use strict";
// Original, local low-poly models. No remote models, textures or camera controls.
(() => {
  const TILT = .72, LIFT = .78;
  const rgb = hex => [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255);
  function environment(map){
    const cave=map.biome==="cave";
    return {cave,ground:cave?"#465260":"#7ea969",path:cave?"#6d6861":"#ddcba0",water:cave?"#285264":"#5caebc",unknown:cave?"#101722":"#152b31",fog:rgb(cave?"#0c1420":"#14262b")};
  }
  function caveLights(map,seen,origin){
    return (map.decorations||[]).filter(item=>["crystal","camp"].includes(item.kind)&&(!seen||seen.has(item.position.join())))
      .sort((a,b)=>Math.hypot(a.position[0]-origin[0],a.position[1]-origin[1])-Math.hypot(b.position[0]-origin[0],b.position[1]-origin[1])).slice(0,8)
      .flatMap(item=>[...item.position,item.kind==="camp"?0:1]);
  }
  class Mesh {
    constructor(){this.data=[];}
    tri(a,b,c,color,light=1){const r=color[0]*light,g=color[1]*light,bv=color[2]*light;this.data.push(a[0],a[1],a[2],r,g,bv,b[0],b[1],b[2],r,g,bv,c[0],c[1],c[2],r,g,bv);}
    quad(a,b,c,d,color,light=1){this.tri(a,b,c,color,light);this.tri(a,c,d,color,light);}
    box(x,y,z,w,h,d,color){
      const a=x-w/2,b=x+w/2,c=z-d/2,e=z+d/2,t=y+h;
      this.quad([a,t,c],[b,t,c],[b,t,e],[a,t,e],color,1.08);
      this.quad([a,y,e],[b,y,e],[b,t,e],[a,t,e],color,.82);
      this.quad([a,y,c],[a,y,e],[a,t,e],[a,t,c],color,.68);
      this.quad([b,y,e],[b,y,c],[b,t,c],[b,t,e],color,.92);
      this.quad([b,y,c],[a,y,c],[a,t,c],[b,t,c],color,.75);
    }
    cone(x,y,z,r,h,color,sides=8){
      for(let i=0;i<sides;i++){
        const a=i*Math.PI*2/sides,b=(i+1)*Math.PI*2/sides;
        this.tri([x+Math.cos(a)*r,y,z+Math.sin(a)*r],[x,y+h,z],[x+Math.cos(b)*r,y,z+Math.sin(b)*r],color,.78+.22*Math.sin(a+.8));
      }
    }
    ball(x,y,z,rx,ry,rz,color){
      const point=(a,b)=>[x+Math.cos(a)*Math.sin(b)*rx,y+Math.cos(b)*ry,z+Math.sin(a)*Math.sin(b)*rz];
      for(let j=0;j<5;j++)for(let i=0;i<8;i++){
        const a=i*Math.PI/4,b=(i+1)*Math.PI/4,c=j*Math.PI/5,d=(j+1)*Math.PI/5;
        this.quad(point(a,c),point(b,c),point(b,d),point(a,d),color,.77+.20*Math.cos(c)+.08*Math.sin(a));
      }
    }
    ring(x,z,r,color,y=.025){
      for(let i=0;i<64;i++){
        const a=i*Math.PI/32,b=(i+1)*Math.PI/32;
        this.quad([x+Math.cos(a)*r,y,z+Math.sin(a)*r],[x+Math.cos(b)*r,y,z+Math.sin(b)*r],
          [x+Math.cos(b)*(r-.035),y,z+Math.sin(b)*(r-.035)],[x+Math.cos(a)*(r-.035),y,z+Math.sin(a)*(r-.035)],color);
      }
    }
  }
  function building(mesh,x,z,w,d){
    mesh.box(x,0,z,w,1.05,d,rgb("#decba3"));
    mesh.box(x,.0,z+d/2+.015,.48,.70,.04,rgb("#785039"));
    for(const offset of [-.30,.30])mesh.box(x+offset*w,.43,z+d/2+.025,.3,.35,.05,rgb("#97ccdd"));
    const a=x-w/2-.15,b=x+w/2+.15,c=z-d/2-.12,e=z+d/2+.12;
    mesh.quad([a,1.05,c],[b,1.05,c],[b,1.7,z],[a,1.7,z],rgb("#b56853"),.8);
    mesh.quad([a,1.7,z],[b,1.7,z],[b,1.05,e],[a,1.05,e],rgb("#db8867"));
    mesh.tri([a,1.05,e],[a,1.7,z],[a,1.05,c],rgb("#ce9c75"));
    mesh.tri([b,1.05,c],[b,1.7,z],[b,1.05,e],rgb("#ce9c75"),.8);
  }
  function sameExploration(a,b){
    if(a===b)return true;
    if(!a||!b||a.size!==b.size)return false;
    for(const cell of b)if(!a.has(cell))return false;
    return true;
  }
  function terrainWindow(camera){
    return {
      x:Math.floor(camera.x/2)*2,z:Math.floor(camera.z/2)*2,
      radiusX:Math.ceil(camera.halfW)+5,radiusZ:Math.ceil(camera.halfH/TILT)+5,
    };
  }
  function scenery(mesh,map,seen,camera){
    const theme=environment(map);
    const radiusX=camera.radiusX??camera.span*.65+5,radiusZ=camera.radiusZ??camera.span*.65+5;
    const visible=(x,z)=>Math.abs(x-camera.x)<=radiusX&&Math.abs(z-camera.z)<=radiusZ;
    const sets=Object.fromEntries(["cover","blocked","paths","water","bridges"].map(key=>[key,new Set((map[key]||[]).map(p=>p.join()))]));
    for(let z=Math.max(0,Math.floor(camera.z-radiusZ));z<Math.min(map.height,camera.z+radiusZ+1);z++)for(let x=Math.max(0,Math.floor(camera.x-radiusX));x<Math.min(map.width,camera.x+radiusX+1);x++){
      if(!visible(x,z))continue;
      const key=`${x},${z}`, known=!seen||seen.has(key),road=sets.paths.has(key),water=sets.water.has(key)&&!sets.bridges.has(key);
      let color=!known?theme.unknown:water?theme.water:sets.bridges.has(key)?"#bb9464":road?theme.path:map.biome==="mountain"?"#87938a":theme.ground;
      const shade=road?1:1+Math.sin((theme.cave?x:Math.floor(x/4))*7+(theme.cave?z:Math.floor(z/4))*3)*(theme.cave?.055:.009),c=rgb(color).map(v=>v*shade);
      const level=known&&water?-.22:0;
      mesh.quad([x-.5,level,z-.5],[x+.5,level,z-.5],[x+.5,level,z+.5],[x-.5,level,z+.5],c);
      if(known&&water){
        for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]]){
          const neighbor=`${x+dx},${z+dz}`;
          if(sets.water.has(neighbor))continue;
          const a=[x+dx*.5-dz*.5,0,z+dz*.5-dx*.5],b=[x+dx*.5+dz*.5,0,z+dz*.5+dx*.5];
          mesh.quad(a,b,[b[0],level,b[2]],[a[0],level,a[2]],rgb(theme.cave?"#323d4d":"#71654f"),dx<0?.68:.90);
        }
        mesh.box(x-.12,-.215,z,.48,.006,.025,rgb("#86c8ce"));
        mesh.box(x+.18,-.215,z+.22,.26,.006,.018,rgb("#75bbc6"));
      }
      if(known&&sets.bridges.has(key)){
        const rotation=(map.bridge_rotations||[]).find(item=>item.position.join()===key)?.rotation||0;
        const turned=rotation===90||rotation===270;
        mesh.box(x,-.13,z,1,.12,1,rgb("#795c3e"));
        for(const offset of [-.38,-.13,.13,.38])mesh.box(x+(turned?offset:0),-.012,z+(turned?0:offset),turned?.018:.98,.012,turned?.98:.018,rgb("#745437"));
      }
      // Expose the earth along the map edge, giving the landscape thickness.
      for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]])if(x+dx<0||x+dx>=map.width||z+dz<0||z+dz>=map.height){
        const a=[x+dx*.5-dz*.5,level,z+dz*.5-dx*.5],b=[x+dx*.5+dz*.5,level,z+dz*.5+dx*.5];
        mesh.quad(a,b,[b[0],-.55,b[2]],[a[0],-.55,a[2]],rgb("#655d49"),.8);
      }
    }
    const decorations=new Set((map.decorations||[]).map(d=>d.position.join()));
    const roofs=new Set((map.decorations||[]).filter(d=>d.kind==="roof").map(d=>d.position.join()));
    while(roofs.size){
      const first=roofs.values().next().value,queue=[first],cells=[];roofs.delete(first);
      for(let i=0;i<queue.length;i++){
        const p=queue[i].split(",").map(Number);cells.push(p);
        for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]]){const key=`${p[0]+dx},${p[1]+dz}`;if(roofs.delete(key))queue.push(key);}
      }
      const xs=cells.map(p=>p[0]),zs=cells.map(p=>p[1]),x=(Math.min(...xs)+Math.max(...xs))/2,z=(Math.min(...zs)+Math.max(...zs))/2;
      if(visible(x,z)&&(!seen||cells.some(p=>seen.has(p.join()))))building(mesh,x,z,Math.max(...xs)-Math.min(...xs)+1,Math.max(...zs)-Math.min(...zs)+1);
    }
    for(const item of map.decorations||[]){
      const [x,z]=item.position;
      if(item.kind==="roof"||!visible(x,z)||seen&&!seen.has(item.position.join()))continue;
      if(theme.cave&&item.kind==="rock"){
        const exposed=[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dz])=>!sets.cover.has(`${x+dx},${z+dz}`));
        const cutaway=z>camera.z+.5,fullHeight=exposed?.75+(Math.sin(x*2.3+z*1.7)+1)*.28:1.35,height=cutaway?Math.min(.55,fullHeight):fullHeight;
        mesh.box(x,0,z,1,height,1,rgb("#454858"));
        if(exposed){if(!cutaway)mesh.cone(x-.12,height,z+.06,.42,.25,rgb("#62616f"),5);mesh.box(x,height*.4,z,.99,.06,1.01,rgb("#333d4d"));}
        continue;
      }
      if(["tree","house","rock","camp"].includes(item.kind))mesh.ball(x+.12,.012,z+.12,.48,.012,.34,rgb(theme.cave?"#1b2331":"#53724c"));
      const rockHeight=item.kind==="rock"?.12+(Math.sin(x*1.7+z*2.1)+1)*.12:0;
      if(rockHeight)mesh.box(x,0,z,.86,rockHeight,.82,rgb("#6f7d6b"));
      const raisedStart=mesh.data.length;
      if(item.kind==="tree"){
        mesh.box(x,0,z,.18,.75,.18,rgb("#8c684b"));
        mesh.ball(x,1.0,z,.60,.65,.53,rgb("#4e8262"));mesh.ball(x-.18,1.25,z-.1,.42,.42,.4,rgb("#8bbf79"));
      }else if(item.kind==="wall"){
        mesh.box(x,0,z,.98,1.0,.98,rgb("#9ba9b1"));
        mesh.box(x-.28,1,z,.28,.20,.9,rgb("#d0d6c6"));mesh.box(x+.28,1,z,.28,.20,.9,rgb("#d0d6c6"));
      }else if(item.kind==="house")building(mesh,x,z,.94,.86);
      else if(item.kind==="rock")mesh.ball(x,.25,z,.50,.48,.44,rgb("#939f9e"));
      else if(item.kind==="crystal"){
        mesh.cone(x,0,z,.24,.9,rgb("#86dbe0"),5);
        if(theme.cave){mesh.cone(x-.23,0,z+.1,.13,.45,rgb("#8196cc"),5);mesh.cone(x+.2,0,z-.12,.11,.6,rgb("#a1e5e0"),5);}
      }
      else if(item.kind==="camp"){
        if(theme.cave){mesh.ball(x,.06,z,.28,.1,.25,rgb("#313b4b"));mesh.box(x,.08,z,.42,.12,.1,rgb("#967454"));mesh.cone(x,.18,z,.15,.48,rgb("#e68a51"),5);mesh.cone(x,.19,z,.08,.30,rgb("#ffe0a0"),5);}
        else mesh.cone(x,0,z,.48,.8,rgb("#ccab78"),4);
      }
      else if(item.kind==="barricade")mesh.box(x,.0,z,.95,.45,.18,rgb("#b48d59"));
      else if(item.kind==="bed"){mesh.box(x,0,z,.5,.22,.8,rgb("#876045"));mesh.box(x,.22,z,.47,.08,.65,rgb("#83b9af"));}
      else if(item.kind==="rack"){mesh.box(x,.1,z,.6,.8,.08,rgb("#886449"));for(const o of [-.16,.16])mesh.box(x+o,.3,z+.08,.04,.65,.04,rgb("#d6e2de"));}
      else if(item.kind==="flowers"){for(const o of [-.18,.12])mesh.ball(x+o,.12,z,.09,.1,.09,rgb(o<0?"#edb0a9":"#f5dfac"));}
      else if(item.kind==="grass"){for(const o of [-.18,.04,.21])mesh.cone(x+o,0,z+o*.5,.035,.16+o*.2,rgb("#557e48"),3);}
      if(rockHeight)for(let i=raisedStart+1;i<mesh.data.length;i+=6)mesh.data[i]+=rockHeight;
    }
    for(const point of map.cover){
      if(!visible(...point)||seen&&!seen.has(point.join())||decorations.has(point.join()))continue;
      mesh.ball(point[0],.2,point[1],.45,.4,.4,rgb(theme.cave?"#454858":"#748978"));
    }
  }
  function appearance(adventure,keys){
    const catalog=adventure.sprites||{}, target=keys.find(k=>catalog.assets?.[catalog.bindings?.[k]]);
    const id=catalog.bindings?.[target]||"chevalier_original";
    const weapon=catalog.equipment?.[target]||"";
    const color=catalog.colors?.[target]||catalog.assets?.[id]?.palette?.[3]||"#718ea1";
    return {id,weapon,color};
  }
  function effectStyle(cue,look={}){
    if(cue.kind==="cast")return {kind:"cast",color:rgb("#d5c8f3"),duration:Math.max(.15,Math.min(12,cue.duration||.5))};
    const support={HEAL:["heal","#8ae8b5"],RESURRECT:["heal","#fff0bd"],BUFF:["buff","#edd58e"],DEBUFF:["debuff","#c795e4"],INVOCATION:["summon","#bba0ed"]}[cue.type];
    if(support)return {kind:support[0],color:rgb(support[1]),duration:1.0};
    const name=cue.name.toLowerCase(),color=/fire|feu|flamme/.test(name)?"#f9b074":/ice|glace|frost/.test(name)?"#9de2ed":/poison|venin/.test(name)?"#b5db7a":"#adccf2";
    if(cue.range<=2)return {kind:"slash",color:rgb(cue.kind==="strike"?"#fff1bb":color),duration:.48};
    return {kind:look.weapon?.includes("bow")?"arrow":"magic",color:rgb(color),duration:.65};
  }
  class CombatEffects {
    constructor(){this.events=[];this.sequence=0;this.context="";}
    ingest(adventure,items,now){
      const battle=adventure.battle,key=`${battle.map.id}:${adventure.encounter_number}`;
      if(key!==this.context){this.events=[];this.sequence=0;this.context=key;}
      for(const cue of battle.visual_events||[]){
        if(cue.id<=this.sequence)continue;this.sequence=cue.id;
        const age=Math.max(0,(battle.visual_now-cue.at)/3);
        if(age>2.5)continue;
        const actor=items.find(a=>a.id===cue.actor||a.id===`world:${cue.actor}`);
        const style=effectStyle(cue,actor?.look);
        if(age>style.duration)continue;
        this.events.push({...cue,...style,start:now-age});
      }
      this.events=this.events.filter(cue=>now-cue.start<cue.duration).slice(-48);
    }
    pose(id,now){
      const cue=this.events.findLast(e=>(e.actor===id||`world:${e.actor}`===id)&&e.kind!=="cast"&&now-e.start<.45);
      return cue?Math.sin(Math.min(1,(now-cue.start)/.45)*Math.PI):0;
    }
    draw(mesh,now,items){
      this.events=this.events.filter(e=>now-e.start<e.duration);
      for(const e of this.events){
        const t=Math.max(0,Math.min(1,(now-e.start)/e.duration)),a=e.source,b=e.destination,c=e.color;
        const actor=items.find(a=>a.id===e.actor||a.id===`world:${e.actor}`);
        if(e.kind==="cast"){
          if(!actor?.unit?.casting&&!actor?.unit?.ability_cast)continue;
          const p=actor.display||a;mesh.ring(...p,.42+.12*Math.sin(t*12),c,.04);
          for(let i=0;i<5;i++){const k=now*3+i*Math.PI*2/5;mesh.ball(p[0]+Math.cos(k)*.40,.5+t*.7,p[1]+Math.sin(k)*.40,.04,.07,.04,c);}
        }else if(e.kind==="slash"){
          const angle=Math.atan2(b[1]-a[1],b[0]-a[0]),radius=Math.min(1.15,Math.hypot(b[0]-a[0],b[1]-a[1]));
          for(let i=0;i<12;i++){
            const k=angle-.9+(t*1.8)-i*.055;
            mesh.ball(a[0]+Math.cos(k)*radius,.7+Math.sin(i*.2)*.12,a[1]+Math.sin(k)*radius,.03,.09,.03,c);
          }
        }else if(e.kind==="arrow"||e.kind==="magic"){
          const flight=Math.min(1,t/.65),x=a[0]+(b[0]-a[0])*flight,z=a[1]+(b[1]-a[1])*flight;
          if(t<.65){
            mesh.ball(x,.72,z,e.kind==="arrow"?.025:.10,e.kind==="arrow"?.025:.1,e.kind==="arrow"?.11:.1,c);
            for(let i=1;i<5;i++){const v=Math.max(0,flight-i*.035);mesh.ball(a[0]+(b[0]-a[0])*v,.72,a[1]+(b[1]-a[1])*v,.025,.025,.025,c);}
          }else for(let i=0;i<8;i++){const k=i*Math.PI/4,r=(t-.65)*1.6;mesh.ball(b[0]+Math.cos(k)*r,.6+(t-.65),b[1]+Math.sin(k)*r,.045,.045,.045,c);}
        }else{
          mesh.ring(...b,.35+t*.50,c,.03);
          if(e.kind==="heal"){
            const h=.35+t;mesh.box(b[0],h,b[1],.10,.30,.05,c);mesh.box(b[0],h+.10,b[1],.30,.10,.05,c);
          }else if(e.kind==="buff"){
            for(const side of [-1,1])mesh.cone(b[0]+side*.23,.25+t*.7,b[1],.09,.15,c,4);
          }else if(e.kind==="summon"){
            mesh.ring(...b,.45+t*.1,c,.08);mesh.cone(b[0],.1,b[1],.20*(1-t),.7,c,8);
          }else for(let i=0;i<5;i++){const k=now*4+i*Math.PI*2/5;mesh.ball(b[0]+Math.cos(k)*.35,1.05+Math.sin(t*Math.PI)*.25,b[1]+Math.sin(k)*.35,.07,.09,.07,c);}
        }
      }
    }
  }
  function model(mesh,actor,time){
    const start=mesh.data.length,[x,z]=actor.display||actor.position,angle=actor.yaw||0,c=Math.cos(angle),s=Math.sin(angle);
    bodyModel(mesh,actor,time);
    for(let i=start;i<mesh.data.length;i+=6){const dx=mesh.data[i]-x,dz=mesh.data[i+2]-z;mesh.data[i]=x+dx*c+dz*s;mesh.data[i+2]=z-dx*s+dz*c;}
  }
  // Species keep their silhouette when the 3D view replaces the pixel sprite.
  function creatureModel(mesh,id,x,z,c,bob,time){
    const dark=rgb("#24363d"),bone=rgb("#e4dcc0");
    const eyes=(y,front,spread=.12)=>{for(const side of [-1,1])mesh.ball(x+side*spread,y,z+front,.04,.055,.035,dark);};
    if(id.includes("objet")){
      if(id.includes("book")){mesh.box(x,.1,z,.48,.08,.34,bone);mesh.box(x,.1,z,.025,.10,.36,c);}
      else if(id.includes("stone")){mesh.box(x,0,z,.48,.14,.38,c);mesh.box(x,.14,z,.34,.62,.18,c);}
      else mesh.box(x,0,z,.48,.40,.40,c);
      return true;
    }
    if(/slime|flame|spirit|ghost/.test(id)){
      if(id.includes("slime")){mesh.ball(x,.24+bob,z,.42,.24-bob,.35,c);eyes(.30+bob,.31);}
      else {mesh.ball(x,.65+bob,z,.25,.42,.22,c);eyes(.78+bob,.21);for(const side of [-1,1])mesh.cone(x+side*.12,.12,z,.10,.33,c,5);
        if(id.includes("flame"))mesh.cone(x,.85+bob,z,.15,.45,c,5);}
      return true;
    }
    if(/mushroom|plant/.test(id)){
      mesh.box(x,0,z,.12,.55,.12,c);
      if(id.includes("mushroom")){mesh.ball(x,.58+bob,z,.48,.22,.40,rgb("#bf6064"));for(const side of [-1,1])mesh.ball(x+side*.19,.72+bob,z+.14,.065,.03,.065,bone);}
      else for(const side of [-1,1]){mesh.ball(x+side*.23,.28+bob,z,.27,.08,.13,c);mesh.cone(x+side*.21,.34,z,.08,.35,c,4);}
      eyes(.43,.10,.04);return true;
    }
    if(/spider|scorpion|beetle/.test(id)){
      const beetle=id.includes("beetle"),scorpion=id.includes("scorpion");
      mesh.ball(x,.25+bob,z,.28,.20,.38,c);mesh.ball(x,.25+bob,z+.35,.17,.14,.16,c);eyes(.29+bob,.48,.07);
      for(const side of [-1,1])for(let i=0;i<(beetle?3:4);i++){
        const legZ=z-.28+i*.18,tip=x+side*(.48+.03*Math.sin(time*8+i));
        mesh.box(x+side*.31,.17,legZ,.24,.06,.05,c);mesh.box(tip,.02,legZ+.06,.055,.18,.055,c);
      }
      if(scorpion){mesh.box(x,.27,z-.44,.09,.38,.09,c);mesh.box(x,.60,z-.36,.09,.09,.26,c);mesh.cone(x,.53,z-.21,.08,.17,bone,4);for(const side of [-1,1])mesh.ball(x+side*.29,.26,z+.48,.14,.08,.18,c);}
      if(beetle){mesh.box(x,.44+bob,z,.025,.025,.42,bone);mesh.ball(x,.40+bob,z-.10,.07,.055,.07,rgb("#f0d269"));}
      return true;
    }
    if(id.includes("golem")){
      mesh.box(x,.25,z,.65,.63,.40,c);mesh.box(x,.88+bob,z,.42,.37,.36,c);
      for(const side of [-1,1]){mesh.box(x+side*.44,.30,z,.21,.55,.24,c);mesh.box(x+side*.19,0,z,.23,.27,.28,c);}
      eyes(1.09+bob,.19);return true;
    }
    const bird=/crow|harpy/.test(id),flying=/crow|harpy|bat|dragon|griffon/.test(id);
    if(bird||id.includes("bat")){
      mesh.ball(x,.59+bob,z,.22,.32,.23,c);mesh.ball(x,.94+bob,z+.07,.20,.20,.19,c);eyes(.99+bob,.24,.07);
      for(const side of [-1,1]){mesh.box(x+side*.10,.07,z,.06,.28,.07,c);mesh.cone(x+side*.34,.53+bob,z,.33,.18+.07*Math.sin(time*7),c,3);}
      if(bird)mesh.cone(x,.85+bob,z+.31,.12,.16,rgb("#d69e45"),4);
      else for(const side of [-1,1])mesh.cone(x+side*.12,1.08+bob,z,.07,.23,c,3);
      return true;
    }
    if(/rat|wolf|boar|lizard|dragon|griffon/.test(id)){
      const rat=id.includes("rat"),lizard=id.includes("lizard"),boar=id.includes("boar");
      mesh.ball(x,.32+bob,z,.30,.23,.48,c);mesh.ball(x,.54+bob,z+.34,.23,.22,.26,c);eyes(.60+bob,.56,.09);
      for(const dx of [-.22,.22])for(const dz of [-.26,.26])mesh.box(x+dx,0,z+dz,.10,.25,.12,c);
      if(rat){for(const side of [-1,1])mesh.ball(x+side*.17,.76+bob,z+.30,.12,.12,.06,rgb("#bf9094"));mesh.box(x,.15,z-.65,.045,.045,.46,rgb("#bf9094"));}
      else if(lizard){mesh.cone(x,.15,z-.43,.18,.36,c,4);for(let i=0;i<4;i++)mesh.cone(x,.51+bob,z-.25+i*.15,.08,.14,bone,4);}
      else for(const side of [-1,1])mesh.cone(x+side*.16,.68+bob,z+.28,.10,.24,c,4);
      if(boar)for(const side of [-1,1])mesh.cone(x+side*.18,.36+bob,z+.53,.05,.21,bone,4);
      if(flying)for(const side of [-1,1])mesh.cone(x+side*.45,.46+bob,z,.36,.25,c,3);
      return true;
    }
    return false;
  }
  function bodyModel(mesh,actor,time){
    const [x,z]=actor.display||actor.position,{id,weapon,color}=actor.look,c=rgb(color),skin=rgb(/gobelin|orc|kobold|troll/.test(id)?"#9ec179":/skeleton|liche|golem/.test(id)?"#d4d5be":"#f0c99f");
    const moving=actor.moving,swing=actor.swing||0,casting=Boolean(actor.unit?.casting||actor.unit?.ability_cast),raise=casting?.26:swing*.22,bob=(moving?Math.sin(time*11+actor.phase)*.035:Math.sin(time*2+actor.phase)*.012)+swing*.06;
    const left=1;
    if(actor.site?.coach_stop){
      const wood=rgb("#89563c"),gold=rgb("#dab879");
      mesh.box(x,0,z,.10,1.65,.10,wood);mesh.box(x,1.25,z,.85,.38,.10,gold);
      if(actor.site.coach_boarding){
        mesh.box(x+.85,.40,z,.85,.80,1.35,rgb("#6b3b36"));mesh.box(x+.85,1.20,z,1,.14,1.55,wood);
        mesh.box(x+.85,.84,z+.68,.50,.40,.025,rgb("#a7ccd0"));
        for(const dx of [.40,1.30])for(const dz of [-.46,.46])mesh.ball(x+dx,.32,z+dz,.20,.27,.27,wood);
        mesh.ball(x+.85,.64,z+1.65,.26,.35,.58,rgb("#af8760"));mesh.ball(x+.85,1.03,z+2.05,.18,.30,.22,wood);
        for(const dx of [.67,1.03])for(const dz of [1.3,1.95])mesh.box(x+dx,0,z+dz,.10,.55,.10,wood);
      }
      return;
    }
    mesh.ball(x,.025,z,.30,.015,.20,rgb("#426d61"));
    if(creatureModel(mesh,id,x,z,c,bob,time))return;
    const leg=moving?Math.sin(time*12+actor.phase)*.10:0;
    mesh.box(x-.12,0,z+leg,.17,.24,.20,rgb("#604d48"));mesh.box(x+.12,0,z-leg,.17,.24,.20,rgb("#604d48"));
    mesh.ball(x,.49+bob,z,.26,.30,.20,c);
    mesh.ball(x,.99+bob,z,.33,.32,.29,skin);
    if(/skeleton|liche/.test(id)){
      mesh.box(x,.81+bob,z+.27,.24,.08,.055,rgb("#e4dcc0"));
      for(let rib=0;rib<3;rib++)mesh.box(x,.38+rib*.09+bob,z+.18,.30,.035,.035,rgb("#e4dcc0"));
    }else mesh.ball(x,1.17+bob,z-.04,.34,.17,.30,rgb(/knight|chevalier|guard/.test(id)?"#aabfca":"#735242"));
    for(const dx of [-.10,.10])mesh.box(x+dx,.97+bob,z+.273,.052,.072,.035,rgb("#29353c"));
    mesh.ball(x-left*.30,.54+bob+raise,z,.10,.13,.11,skin);mesh.ball(x+left*(.30+swing*.16),.56+bob+raise,z,.10,.13,.11,skin);
    if(/mage|pretre|priest|necromancer|liche/.test(id))mesh.cone(x,1.22+bob,z,.30,.40,c,8);
    if(weapon.includes("bow")){
      mesh.box(x+left*.42,.33+bob,z,.055,.55,.045,rgb("#88623d"));
      mesh.box(x+left*.50,.34+bob,z,.025,.52,.025,rgb("#e5d7b2"));
    }else if(/staff|wand/.test(weapon)){
      mesh.box(x+left*.40,.1,z,.06,.95,.06,rgb("#90734c"));mesh.ball(x+left*.40,1.10,z,.12,.15,.12,rgb("#b7b1ed"));
    }else if(/axe|hammer|pick/.test(weapon)){
      const hand=x+left*(.42+swing*.16),metal=rgb("#d1dfdc");
      mesh.box(hand,.12+bob,z,.06,.70,.06,rgb("#927049"));
      if(weapon.includes("axe"))mesh.ball(hand+.10,.77+bob,z,.18,.20,.055,metal);
      else if(weapon.includes("hammer"))mesh.box(hand,.74+bob,z,.37,.21,.18,metal);
      else {mesh.box(hand,.78+bob,z,.46,.07,.07,metal);mesh.cone(hand-.23,.62+bob,z,.05,.20,metal,4);}
    }else if(weapon.includes("spear")){
      mesh.box(x+left*.42,.05,z,.05,1.12,.05,rgb("#927049"));mesh.cone(x+left*.42,1.17,z,.09,.27,rgb("#d1dfdc"),4);
    }else if(weapon){
      mesh.box(x+left*(.42+swing*.16),.37+bob+swing*.22,z,.075,weapon.includes("dagger")?.28:.62,.05,rgb("#e1e8df"));mesh.box(x+left*(.42+swing*.16),.38+bob+swing*.22,z,.24,.05,.08,rgb("#d2b677"));
      if(weapon.includes("shield"))mesh.ball(x-left*.37,.54+bob,z+.03,.20,.25,.07,rgb("#859eab"));
    }
  }
  function actors(adventure,me){
    const result=[],battle=adventure.battle;
    const add=(id,p,name,keys,extra={})=>result.push({id,position:p,name,look:appearance(adventure,keys),phase:result.length*.7,...extra});
    for(const p of adventure.players){const unit=battle.players[p.id];add(p.id,unit.position,p.id===me.id?"Vous":p.name,[`class:${p.class_name}`],{hp:p.hp,max_hp:p.max_hp,unit,hero:p.id===me.id});const weapon=typeof equippedWeaponSprite==="function"?equippedWeaponSprite(p):"";if(weapon)result.at(-1).look.weapon=weapon;}
    for(const mob of adventure.mobs)add(mob.combat_id,mob.position,mob.name,[`mob:${mob.mob_id}`],{hp:mob.stats.hp.current,max_hp:mob.stats.hp.max,enemy:true,unit:mob});
    for(const [id,s] of Object.entries({...battle.summons,...battle.companions}))add(id,s.position,s.name,[`mob:${s.mob_id}`,`class:${s.class_name}`],{hp:s.hp,max_hp:s.max_hp,unit:s});
    for(const site of battle.map.sites||[])add(`site:${site.id}`,site.position,site.name,[`npc:${site.id}`],{site});
    for(const corpse of battle.corpses||[]){add(corpse.id,corpse.position,corpse.name,[],{corpse:true});result.at(-1).look={id:"objet_cargo",weapon:"",color:"#a88861"};}
    for(const a of adventure.living_world?.nearby||[])if(a.map===battle.map.id&&!["monsters","raiders"].includes(a.kind)&&!(a.kind==="guards"&&!a.role))add(`world:${a.id}`,a.position,a.name,[`npc:${a.id}`,`ambient:guard_${a.role}`,`ambient:${a.kind}`],{hp:a.hp,max_hp:a.max_hp,unit:a});
    for(const p of typeof presenceState!=="undefined"?presenceState?.nearby||[]:[])if(p.position&&(p.map===adventure.field_map||p.map===battle.map.id)&&!result.some(a=>a.id===p.id))add(p.id,p.position,p.name,["class:Knight"]);
    return result;
  }
  // Interpolate actual steps behind the simulation so late step updates do not
  // produce a stop at every cell. Never extrapolate through a wall or a fight.
  class GuardTrack {
    constructor(position,at){this.samples=[{position:[...position],at}];this.delay=1000;}
    push(position,at){
      const last=this.samples.at(-1),distance=Math.hypot(...position.map((v,i)=>v-last.position[i]));
      // Retain occasional stationary anchors for a smooth restart after a real
      // stop, without inserting identical snapshots between normal steps.
      if(distance<.000001&&at-last.at<800)return;
      if(distance>3){this.samples=[{position:[...position],at}];return;}
      this.samples.push({position:[...position],at});
      if(this.samples.length>32)this.samples.shift();
    }
    sample(at){
      const time=at-this.delay;
      while(this.samples.length>2&&this.samples[1].at<=time)this.samples.shift();
      const [a,b]=this.samples;
      if(!b||time<=a.at)return [...a.position];
      const mix=Math.max(0,Math.min(1,(time-a.at)/Math.max(1,b.at-a.at)));
      return a.position.map((v,i)=>v+(b.position[i]-v)*mix);
    }
  }
  class Scene {
    constructor(parent){
      this.parent=parent;this.root=document.createElement("div");this.root.className="rpg-scene3d";
      this.canvas=document.createElement("canvas");this.canvas.className="rpg-canvas3d";this.canvas.tabIndex=0;
      this.canvas.setAttribute("aria-label","Monde en 3D, caméra fixe. Déplacements : ZQSD, WASD ou flèches. Espace : attaquer.");
      this.labels=document.createElement("div");this.labels.className="scene3d-labels";
      this.attack=document.createElement("button");this.attack.className="scene3d-attack";this.attack.type="button";
      this.attack.textContent="⚔ Attaquer";this.attack.onclick=()=>attack();
      this.help=document.createElement("span");this.help.className="scene3d-help";this.help.textContent="ZQSD / WASD · Espace : attaque";
      this.root.append(this.canvas,this.labels,this.help);
      this.gl=this.canvas.getContext("webgl",{alpha:false,antialias:true,preserveDrawingBuffer:false});
      if(!this.gl)throw Error("WebGL unavailable");
      const gl=this.gl;
      const compile=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
      this.program=gl.createProgram();
      gl.attachShader(this.program,compile(gl.VERTEX_SHADER,`attribute vec3 p;attribute vec3 c;uniform vec4 camera;varying vec3 color;varying vec3 world;void main(){vec3 v=p-vec3(camera.x,0.0,camera.y);gl_Position=vec4(v.x/camera.z,(-v.z*0.72+v.y*0.78)/camera.w,-(v.z*0.78+v.y*0.72)/128.0,1.0);color=c;world=p;}`));
      gl.attachShader(this.program,compile(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 color;varying vec3 world;uniform float underground;uniform vec2 observer;uniform vec3 mist;uniform vec3 lightSources[8];void main(){vec3 result=color;if(underground>0.5){float lantern=1.0-smoothstep(1.5,8.0,distance(world.xz,observer));vec3 illumination=vec3(0.42,0.49,0.58)+lantern*vec3(0.60,0.51,0.36);for(int i=0;i<8;i++){float halo=max(0.0,1.0-distance(world.xz,lightSources[i].xy)/3.6);vec3 glow=mix(vec3(0.85,0.35,0.12),vec3(0.18,0.46,0.65),lightSources[i].z);illumination+=halo*halo*glow;}float haze=smoothstep(4.0,18.0,distance(world.xz,observer))*0.65;result=mix(color*min(illumination,vec3(1.4)),mist,haze);}gl_FragColor=vec4(result,1.0);}`));
      gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(this.program));
      this.staticBuffer=gl.createBuffer();this.dynamicBuffer=gl.createBuffer();this.cameraUniform=gl.getUniformLocation(this.program,"camera");
      this.environmentUniforms=Object.fromEntries(["underground","observer","mist","lightSources[0]"].map(key=>[key,gl.getUniformLocation(this.program,key)]));
      this.camera={x:0,z:0,span:22,halfW:11,halfH:7};this.previous=new Map();this.nodes=new Map();this.effects=new CombatEffects();this.last=0;this.stats={cameraLocked:true,azimuth:0,tilt:TILT};
      this.canvas.scene3D=this;
      this.canvas.oncontextmenu=e=>e.preventDefault();
      this.canvas.onwheel=e=>{e.preventDefault();adjustFieldCamera(e.deltaY>0?"out":"in");};
      this.canvas.onclick=e=>{
        this.canvas.focus({preventScroll:true});
        const rect=this.canvas.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*2-1,y=1-(e.clientY-rect.top)/rect.height*2;
        const hit=(this.items||[]).filter(a=>!a.hero).map(a=>{const p=this.project(a.display||a.position,.55);return {a,d:Math.hypot((p[0]-(x+1)/2)*rect.width,(p[1]-(1-y)/2)*rect.height)};}).sort((a,b)=>a.d-b.d)[0];
        if(hit?.d<24){if(hit.a.site)moveControlled(this.adventure,this.me,hit.a.position);else selectEntity(hit.a.id);return;}
        const destination=[this.camera.x+x*this.camera.halfW,this.camera.z-y*this.camera.halfH/TILT];
        moveControlled(this.adventure,this.me,destination.map(Math.round));
      };
      this.canvas.addEventListener("webglcontextlost",e=>{e.preventDefault();this.lost=true;});
      this.canvas.addEventListener("webglcontextrestored",()=>{this.root.remove();});
      parent.append(this.root);this.frame=requestAnimationFrame(t=>this.draw(t));
    }
    update(adventure,me){
      const received=performance.now();
      if(globalThis.RPGMotion?.sync(adventure,me,received)===false)return;
      const previousReceived=this.received,previousMap=this.adventure?.battle.map;
      this.adventure=adventure;this.me=me;this.received=received;
      const now=this.received/1000;
      this.items=actors(adventure,me).map(a=>{
        const prev=this.previous.get(a.id),delta=prev?Math.hypot(a.position[0]-prev.position[0],a.position[1]-prev.position[1]):0;
        const changed=delta>.000001;
        a.from=changed?(prev?.display||prev?.position||a.position):(prev?.from||a.position);
        a.sampleAt=changed||!prev?this.received:prev.sampleAt;
        a.interpolation=changed?Math.max(80,Math.min(450,this.received-(prev?.sampleAt||previousReceived||this.received-100))):(prev?.interpolation||100);
        if(a.unit?.kind==="guards"){
          a.track=prev?.track||new GuardTrack(a.position,this.received);
          a.track.push(a.position,this.received);a.lastDisplay=prev?.display;
        }
        if(a.enemy&&!adventure.battle.continuous_agents)a.interpolation=Math.max(a.interpolation,Math.min(650,Math.max(0,(a.unit.next_move-adventure.battle.visual_now)/3)*1000));
        if(delta>3)a.from=a.position;
        a.moving=delta>.005||(prev?.display&&Math.hypot(...a.position.map((v,i)=>v-prev.display[i]))>.005)||a.unit?.route?.length||(a.unit?.motion_until>adventure.battle.visual_now&&Math.hypot(...(a.unit?.motion_axis||[0,0]))>0);
        const dx=a.position[0]-(prev?.position[0]??a.position[0]),dz=a.position[1]-(prev?.position[1]??a.position[1]);
        a.targetYaw=changed?Math.atan2(dx,dz):(prev?.targetYaw||0);a.yaw=prev?.yaw??a.targetYaw;
        a.received=now;this.previous.set(a.id,a);return a;
      });
      this.effects.ingest(adventure,this.items,now);
      const retained=new Set(this.items.map(a=>a.id));for(const key of this.previous.keys())if(!retained.has(key))this.previous.delete(key);
      const span=typeof fieldCamera!=="undefined"?fieldCamera?.span:22;
      this.camera.span=Math.max(12,Math.min(36,span||22));
      const hero=this.items.find(a=>a.hero);
      if(typeof fieldCamera!=="undefined"&&fieldCamera?.follow===false){this.camera.x=fieldCamera.x;this.camera.z=fieldCamera.y;}
      else if(hero&&previousMap?.id!==adventure.battle.map.id){this.camera.x=hero.position[0];this.camera.z=hero.position[1];}
      const seen=adventure.field_map?new Set((adventure.battle.explored||[]).map(p=>p.join())):null;
      if(!sameExploration(this.seen,seen)){this.seen=seen;this.terrainKey=null;}
      this.root.dataset.biome=adventure.battle.map.biome||"forest";
      this.attack.textContent=`⚔ Attaquer · portée ${me.attack_range}`;
      this.help.textContent=globalThis.RPGKeybindings?.hint()||`ZQSD / WASD · Espace : attaque · Portée ${me.attack_range}`;
      this.canvas.setAttribute("aria-label", "Monde en 3D. " + this.help.textContent);
      this.attack.disabled=me.hp<=0||me.stunned||me.casting||me.cooldown_real_seconds>0;
    }
    updateTerrain(){
      const map=this.adventure.battle.map,window=terrainWindow(this.camera);
      const key=`${map.id}:${map.biome}:${map.terrain_version}:${map.width}:${map.height}:${window.x}:${window.z}:${window.radiusX}:${window.radiusZ}`;
      if(key===this.terrainKey)return;
      const mesh=new Mesh();scenery(mesh,map,this.seen,window);
      this.upload(this.staticBuffer,mesh);this.staticCount=mesh.data.length/6;this.terrainKey=key;
    }
    upload(buffer,mesh){const gl=this.gl;gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(mesh.data),gl.DYNAMIC_DRAW);}
    buffer(buffer,count){
      const gl=this.gl;gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
      for(const [key,offset] of [["p",0],["c",12]]){const id=gl.getAttribLocation(this.program,key);gl.enableVertexAttribArray(id);gl.vertexAttribPointer(id,3,gl.FLOAT,false,24,offset);}
      gl.drawArrays(gl.TRIANGLES,0,count);
    }
    project(position,height=0){return [(position[0]-this.camera.x)/this.camera.halfW*.5+.5,((position[1]-this.camera.z)*TILT-height*LIFT)/this.camera.halfH*.5+.5];}
    draw(ms){
      if(!this.root.isConnected){this.dispose();return;}
      this.frame=requestAnimationFrame(t=>this.draw(t));
      if(ms-this.last<15||this.lost||document.hidden||!this.items||!this.root.getClientRects().length)return;
      this.last=ms;const gl=this.gl,rect=this.root.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,1.75);
      if(!rect.width||!rect.height)return;
      if(this.canvas.width!==Math.round(rect.width*ratio)||this.canvas.height!==Math.round(rect.height*ratio)){this.canvas.width=Math.round(rect.width*ratio);this.canvas.height=Math.round(rect.height*ratio);}
      this.camera.halfW=this.camera.span/2;this.camera.halfH=this.camera.halfW*rect.height/rect.width;
      const t=ms/1000,mesh=new Mesh(),visible=[];
      for(const a of this.items){
        const mix=Math.min(1,(ms-a.sampleAt)/a.interpolation);a.display=a.position.map((v,i)=>a.from[i]+(v-a.from[i])*mix);
        if(a.track){
          const before=a.lastDisplay||a.display;a.display=a.track.sample(ms);
          const dx=a.display[0]-before[0],dz=a.display[1]-before[1];
          a.moving=Math.hypot(dx,dz)>.000001;
          if(a.moving)a.targetYaw=Math.atan2(dx,dz);
          a.lastDisplay=[...a.display];
        }
        if(a.hero&&globalThis.RPGMotion){a.display=RPGMotion.sample(this.adventure,this.me,ms)||a.display;a.moving=RPGMotion.axis.some(Boolean)||Boolean(a.unit?.route?.length);}
        if(a.hero&&globalThis.RPGMotion?.axis.some(Boolean)){const [dx,dz]=RPGMotion.axis;a.targetYaw=Math.atan2(dx,dz);}
        const turn=Math.atan2(Math.sin(a.targetYaw-a.yaw),Math.cos(a.targetYaw-a.yaw));a.yaw+=turn*.35;
      }
      const followed=this.items.find(a=>a.hero);
      if(followed&&(typeof fieldCamera==="undefined"||fieldCamera?.follow!==false)){
        this.camera.x=followed.display[0];this.camera.z=followed.display[1];
      }
      for(const a of this.items){
        if(Math.abs(a.display[0]-this.camera.x)>this.camera.halfW+2||Math.abs(a.display[1]-this.camera.z)>this.camera.halfH/TILT+3)continue;
        if(this.seen&&!this.seen.has(a.position.map(Math.round).join()))continue;
        if(a.hp!==undefined&&a.hp<=0)continue;
        a.swing=this.effects.pose(a.id,t);model(mesh,a,t);visible.push(a);
      }
      this.effects.draw(mesh,t,this.items);
      this.stats.effects=this.effects.events.length;
      const hero=visible.find(a=>a.hero);
      if(hero){
        mesh.ring(...hero.display,this.me.attack_range,rgb("#e6d6a1"));
        mesh.ring(...hero.display,.38,rgb("#f4e7bd"),.03);
      }
      for(const gate of this.adventure.battle.map.exits||[]){
        if(this.seen&&!this.seen.has(gate.position.join()))continue;
        mesh.ring(...gate.position,.40,rgb("#a6d6c9"));
      }
      const target=visible.find(a=>typeof focusedMob!=="undefined"&&a.id===focusedMob);
      if(target)mesh.ring(...target.display,.42,rgb("#ed9b8a"),.035);
      this.updateTerrain();
      this.upload(this.dynamicBuffer,mesh);
      gl.viewport(0,0,this.canvas.width,this.canvas.height);
      gl.enable(gl.DEPTH_TEST);gl.useProgram(this.program);gl.uniform4f(this.cameraUniform,this.camera.x,this.camera.z,this.camera.halfW,this.camera.halfH);
      const theme=environment(this.adventure.battle.map),observer=hero?.display||[this.camera.x,this.camera.z],lights=theme.cave?caveLights(this.adventure.battle.map,this.seen,observer):[],sources=new Float32Array(24);
      for(let i=0;i<8;i++){sources[i*3]=10000;sources[i*3+1]=10000;}sources.set(lights);
      gl.uniform1f(this.environmentUniforms.underground,theme.cave?1:0);gl.uniform2f(this.environmentUniforms.observer,...observer);gl.uniform3fv(this.environmentUniforms.mist,theme.fog);gl.uniform3fv(this.environmentUniforms["lightSources[0]"],sources);
      if(theme.cave)gl.clearColor(...theme.fog,1);else gl.clearColor(.08,.15,.17,1);
      gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);this.stats.biome=this.root.dataset.biome;this.stats.lights=lights.length/3;
      this.buffer(this.staticBuffer,this.staticCount);this.buffer(this.dynamicBuffer,mesh.data.length/6);
      this.stats.vertices=this.staticCount+mesh.data.length/6;this.stats.models=visible.length;this.stats.frames=(this.stats.frames||0)+1;
      const used=new Set(),occupied=[];
      for(const a of visible){
        used.add(a.id);let node=this.nodes.get(a.id);
        if(!node){node=document.createElement("button");node.type="button";node.className="scene3d-label";node.dataset.entity=a.id;this.labels.append(node);this.nodes.set(a.id,node);}
        const [x,y]=this.project(a.display,1.48);
        node.classList.toggle("scene3d-enemy",Boolean(a.enemy));
        const caption=a.unit?.kind==="guards"?(a.unit.role==="archer"?"Archer":"Chevalier"):a.name;
        node.title=a.name;node.textContent=caption+(a.max_hp?` · ${Math.max(0,Math.ceil(a.hp))}/${a.max_hp}`:"");
        const labelWidth=Math.min(220,Math.max(60,node.textContent.length*6+14)),px=x*rect.width;
        let py=y*rect.height;
        for(let row=0;row<5&&occupied.some(box=>Math.abs(box.x-px)<(box.width+labelWidth)/2+4&&Math.abs(box.y-py)<19);row++)py-=20;
        occupied.push({x:px,y:py,width:labelWidth});node.style.left=`${px}px`;node.style.top=`${py}px`;
        node.classList.toggle("selected",typeof focusedMob!=="undefined"&&focusedMob===a.id);
        node.onclick=()=>{if(a.site)moveControlled(this.adventure,this.me,a.position);else selectEntity(a.id);};
        node.ondblclick=()=>{if(a.enemy)attack(a.id);else moveControlled(this.adventure,this.me,a.position);};
      }
      for(const [key,node] of this.nodes)if(!used.has(key)){node.remove();this.nodes.delete(key);}
    }
    dispose(){cancelAnimationFrame(this.frame);for(const buffer of [this.staticBuffer,this.dynamicBuffer])this.gl.deleteBuffer(buffer);this.gl.deleteProgram(this.program);this.root.remove();}
  }
  function attack(preferred){
    const adventure=typeof session!=="undefined"?session?.tutorial:null;if(!adventure?.battle||busy)return;
    const me=adventure.players.find(p=>p.id===session.me);if(!me||me.hp<=0||me.stunned||me.casting||me.cooldown_real_seconds>0)return;
    const source=globalThis.RPGMotion?.position?.(adventure,me.id)||adventure.battle.players[me.id].position;
    const targets=adventure.mobs.filter(m=>m.stats.hp.current>0&&battleAllowed(adventure,me.id,m.combat_id,me.attack_range)).sort((a,b)=>Math.hypot(...a.position.map((v,i)=>v-source[i]))-Math.hypot(...b.position.map((v,i)=>v-source[i])));
    const target=targets.find(m=>m.combat_id===(preferred||focusedMob))||targets[0];
    if(target)tutorialCommand("strike",{target:target.combat_id});else message("Aucun ennemi à portée.");
  }
  globalThis.renderRpgScene3D=(adventure,me)=>{
    const parent=document.getElementById("world-map");let node=parent.querySelector(".rpg-canvas3d");
    let scene;
    try{
      scene=node?.scene3D?.root.isConnected?node.scene3D:new Scene(parent);
      scene.update(adventure,me);parent.classList.add("has-scene3d");
      for(const child of [...parent.children])if(child!==scene.root)child.remove();
      return true;
    }catch(error){scene?.dispose();parent.classList.remove("has-scene3d");parent.dataset.renderer="svg";return false;}
  };
  globalThis.RPGScene3D={Mesh,scenery,terrainWindow,sameExploration,environment,caveLights,CombatEffects,GuardTrack,effectStyle,model,actors,project:(position,camera,height=0)=>[(position[0]-camera.x)/camera.halfW*.5+.5,((position[1]-camera.z)*TILT-height*LIFT)/camera.halfH*.5+.5],cameraAngle:Object.freeze({azimuth:0,tilt:TILT}),attack};
})();
