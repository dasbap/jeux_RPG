"use strict";
// Pixel data is validated in the project catalogue; no remote images are used.
const spriteImages = new Map();
const spriteDirections = new Map();
function spriteFacing(adventure, id, unit, target=null) {
  const position=unit.position, key=`${adventure.field_map||adventure.battle?.map?.id||""}:${id}`;
  const previous=spriteDirections.get(key);
  const moved=previous && (position[0]!==previous.position[0]||position[1]!==previous.position[1]);
  const aim=moved?position:unit.route?.[0]||target;
  const origin=moved?previous.position:position;
  const dx=aim?aim[0]-origin[0]:0;
  const facing=dx<0?"left":dx>0?"right":previous?.facing||"right";
  spriteDirections.set(key,{position:[...position],facing});
  if(spriteDirections.size>256)spriteDirections.delete(spriteDirections.keys().next().value);
  return facing;
}
function spriteDataUri(sprite, weapon=null, tint=null) {
  const key=JSON.stringify([sprite,weapon,tint]);
  if(spriteImages.has(key))return spriteImages.get(key);
  const layerSvg=(layer,kind)=>{
  const count=layer.frames.length, times=Array.from({length:count+1},(_,i)=>i/count).join(";");
  return `<g data-layer="${kind}">`+layer.frames.map((rows,index)=>{
    const paths=new Map();
    rows.forEach((row,y)=>{
      for(let x=0;x<row.length;) {
        const digit=row[x],start=x;while(x<row.length&&row[x]===digit)x++;
        if(digit!=="0") paths.set(digit,(paths.get(digit)||"")+`M${start} ${y}h${x-start}v1h-${x-start}z`);
      }
    });
    const palette=[...layer.palette];
    if(kind==="body"&&tint) {
      const shadow=color=>"#"+[1,3,5].map(start=>Math.round(parseInt(color.slice(start,start+2),16)*.65).toString(16).padStart(2,"0")).join("");
      if(palette[14]&&palette[3]&&palette[14]===shadow(palette[3]))palette[14]=shadow(tint);
      palette[3]=tint;
      palette[4]="#"+[1,3,5].map(start=>Math.round(parseInt(tint.slice(start,start+2),16)*.7+255*.3).toString(16).padStart(2,"0")).join("");
    }
    const drawing=[...paths].map(([digit,path])=>`<path fill="${palette[parseInt(digit,16)]}" d="${path}"/>`).join("");
    const states=Array.from({length:count+1},(_,i)=>(i%count)===index?"visible":"hidden").join(";");
    return `<g visibility="${index?"hidden":"visible"}">${drawing}${count>1?`<animate attributeName="visibility" values="${states}" keyTimes="${times}" calcMode="discrete" dur="${layer.frame_ms*count}ms" repeatCount="indefinite"/>`:""}</g>`;
  }).join("")+"</g>";};
  const frames=layerSvg(sprite,"body")+(weapon?layerSvg(weapon,"weapon"):"");
  const value="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${sprite.width}" height="${sprite.height}" viewBox="0 0 ${sprite.width} ${sprite.height}" shape-rendering="crispEdges">${frames}</svg>`);
  spriteImages.set(key,value);if(spriteImages.size>64)spriteImages.delete(spriteImages.keys().next().value);
  return value;
}
function equippedWeaponSprite(player){return {sword:"arme_sword",bow:"arme_bow",staff:"arme_staff"}[(player?.gear||[]).find(item=>item.slot==="weapon")?.weapon_type]||"";}
function entitySprite(adventure, keys, element, position, size=36, facing="right", weaponOverride="") {
  const catalog=adventure.sprites;
  const target=keys.find(key=>catalog?.assets[catalog?.bindings?.[key]]);
  const id=catalog?.bindings?.[target], sprite=catalog?.assets[id];
  if(!sprite)return null;
  const width=size*sprite.width/Math.max(sprite.width,sprite.height),height=size*sprite.height/Math.max(sprite.width,sprite.height);
  const override=catalog?.assets[weaponOverride];
  const weaponId=override?.layer==="weapon"&&override.width===sprite.width&&override.height===sprite.height?weaponOverride:catalog?.equipment?.[target],weapon=catalog?.assets[weaponId];
  const tint=catalog?.colors?.[target];
  const attrs={href:spriteDataUri(sprite,weapon||null,tint||null),x:position[0]*40+20-width/2,y:position[1]*40+20-height/2,width,height,"data-sprite":id,"data-weapon":weaponId||"","data-tint":tint||"","data-facing":facing,"aria-label":sprite.name,"image-rendering":"pixelated"};
  if(facing==="left")attrs.transform=`translate(${position[0]*80+40} 0) scale(-1 1)`;
  return element("image",attrs);
}
function spriteThumbnail(adventure,keys) {
  const element=(tag,attrs)=>{const node=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,value);return node;};
  const image=entitySprite(adventure,keys,element,[0,0]);
  if(!image)return null;
  const svg=element("svg",{viewBox:"0 0 40 40",width:64,height:64,"aria-hidden":"true"});svg.append(image);return svg;
}
