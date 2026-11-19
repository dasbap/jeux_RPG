"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),{chromium}=require("../.data/browser-tools/node_modules/playwright");
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,"utf8")),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:940}}),errors=[];
  await context.route("**/*",route=>new URL(route.request().url()).origin===config.url?route.continue():route.abort());
  await context.addInitScript(token=>sessionStorage.setItem("rpg-token",token),config.token);
  const page=await context.newPage();page.on("pageerror",error=>errors.push(error.message));
  await page.goto(config.url);await page.waitForFunction(()=>typeof session!=="undefined" && Boolean(session?.tutorial) && typeof renderGame==="function").catch(async error=>{await page.screenshot({path:path.resolve(".data/cave-browser-failure.png")});console.error(JSON.stringify({errors,text:(await page.locator("body").innerText()).slice(-3500)}));throw error;});
  await page.evaluate(()=>{refresh=async()=>{};scheduleRefresh=()=>{};});
  const show=async(id,suffix="")=>{
    await page.evaluate(adventure=>{session={...session,tutorial:adventure};RPGMotion.rebase();fieldCamera={x:adventure.battle.players[session.me].position[0],y:adventure.battle.players[session.me].position[1],span:22,follow:true};renderGame(adventure);},config.snapshots[id]);
    await page.waitForFunction(biome=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.biome===biome,id==="forest"?"forest":"cave");
    const state=await page.evaluate(()=>{const scene=document.querySelector(".rpg-canvas3d").scene3D,gl=scene.gl;return {biome:scene.stats.biome,lights:scene.stats.lights,underground:gl.getUniform(scene.program,scene.environmentUniforms.underground),error:gl.getError(),vertices:scene.stats.vertices};});
    assert.equal(state.error,0);assert(state.vertices>1000);
    assert.equal(await page.locator("#hud-minimap").getAttribute("data-biome"),id==="forest"?"forest":"cave");
    if(id!=="forest"){assert.equal(state.underground,1);assert(state.lights>0);}else{assert.equal(state.underground,0);assert.equal(state.lights,0);}
    await page.screenshot({path:path.resolve(`.data/${id}-3d${suffix}.png`)});return state;
  };
  const entry=await show("cave_1"),depths=await show("cave_2");await show("cave_8");await show("forest");
  await show("cave_1");
  await page.evaluate(()=>{mapPlace="grotte_oublies";showView("map",{toggle:false});});
  const maze=page.locator('svg[data-map="detail:grotte_oublies"]');
  await maze.waitFor({state:"visible"});
  assert.equal(await maze.locator("g[data-point]").count(),12);
  assert.equal(await maze.locator("line.known-route").count(),22); // 21 passages plus region entry
  await maze.screenshot({path:path.resolve(".data/forgotten-labyrinth-atlas.png")});
  await page.locator('svg[data-map="general"]').last().screenshot({path:path.resolve(".data/world-atlas.png")});
  await page.evaluate(()=>{mapPlace="zone_rosee";showView("map",{toggle:false});});
  assert.equal(await page.locator('svg[data-map="detail:zone_rosee"] g[data-point]').count(),14);
  await page.locator('svg[data-map="detail:zone_rosee"]').screenshot({path:path.resolve(".data/rosee-atlas.png")});
  await page.evaluate(()=>showView("map",{toggle:true}));
  await page.setViewportSize({width:390,height:844});await show("cave_1","-mobile");
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,entry,depths,checks:["actual WebGL shaders","entrance, boss and new labyrinth room", "twelve-room atlas and 21 passages", "Rosee atlas","light sources","return to outdoor lighting","mobile"]}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
