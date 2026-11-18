"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),{chromium}=require("../.data/browser-tools/node_modules/playwright");
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,"utf8")),browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:"block"}),errors=[],requests=[];
  await context.route("**/*",route=>new URL(route.request().url()).origin===config.url?route.continue():route.abort());
  await context.addInitScript(token=>sessionStorage.setItem("rpg-token",token),config.token);
  const page=await context.newPage();page.on("pageerror",error=>errors.push(error.message));
  page.on("request",request=>{if(request.url().endsWith("/api/commands"))requests.push(request.postDataJSON()?.action);});
  await page.goto(config.url);await page.waitForFunction(()=>Boolean(session?.tutorial));
  await page.evaluate(()=>showView("equipment",{toggle:false}));
  const worn=()=>page.locator('#equipment-view .gear-card[data-recipe="veste"] [data-equipment-action="unequip"]');
  await worn().click();
  const stored=page.locator('#equipment-view .gear-card[data-recipe="veste"] [data-equipment-action="equip"]');await stored.waitFor();await stored.click();await worn().waitFor();
  await page.locator('#equipment-view .gear-card[data-recipe="manteau_veille"] [data-equipment-action="equip"]').click();
  await page.locator('#equipment-view .gear-card[data-recipe="manteau_veille"] [data-equipment-action="unequip"]').waitFor();
  await page.locator('#equipment-view .gear-card[data-recipe="veste"] [data-equipment-action="equip"]').click();await worn().waitFor();
  await page.reload();await page.waitForFunction(()=>Boolean(session?.tutorial));await page.evaluate(()=>showView("equipment",{toggle:false}));await worn().waitFor();
  await page.locator('#equipment-view .gear-card[data-recipe="manteau_veille"] summary').click();
  const capture=async name=>{await page.evaluate(()=>{document.querySelector('.adventure-grid').scrollTop=0;window.scrollTo(0,0);});await page.screenshot({path:path.resolve(`.data/menu-${name}.png`),animations:"disabled"});};
  await capture("equipment");
  const setText=await page.locator('#equipment-view [data-recipe="veste"] .item-set-bonuses').textContent();
  await page.evaluate(()=>showView("inventory",{toggle:false}));
  assert.equal(await page.locator('#inventory-view [data-recipe="veste"] .item-set-bonuses').textContent(),setText);
  await capture("inventory");
  await page.evaluate(()=>openForge());await page.locator("#craft-view").waitFor();
  assert.equal(await page.locator('#forge-catalogue [data-recipe="veste"] .item-set-bonuses').textContent(),setText);
  assert(await page.locator('#forge-catalogue [data-recipe="jambieres"] .item-set-tier').count()>0);
  await page.screenshot({path:path.resolve(".data/menu-forge.png"),animations:"disabled"});await page.locator("#forge-close").click();
  await page.evaluate(()=>showView("quest",{toggle:false}));await page.locator("#quest-list .quest-card").first().waitFor();
  await page.locator('#quest-status-tabs [data-status="completed"]').click();assert(await page.locator(".quest-completed").count()>0);
  await page.locator('#quest-status-tabs [data-status="all"]').click();
  await capture("quests");
  await page.evaluate(()=>showView("bestiary",{toggle:false}));await page.locator(".bestiary-selected").waitFor();
  await page.locator('.bestiary-entry[data-mob="orc"]').click();assert.equal(await page.locator(".bestiary-selected").getAttribute("data-mob"),"orc");
  assert.equal(await page.locator('.bestiary-entry[aria-pressed="true"]').count(),1);
  await capture("bestiary");
  const audit=async()=>{
    const report=await page.evaluate(()=>{
      const nodes=[...document.querySelectorAll('[id]')],duplicates=nodes.map(n=>n.id).filter((id,i,ids)=>ids.indexOf(id)!==i);
      const menus=[...document.querySelectorAll('.adventure-grid .atlas-menu')].filter(n=>n.checkVisibility()).map(n=>n.id);
      const frame=document.querySelector('.adventure-grid');
      return {duplicates,menus,pageOverflow:document.documentElement.scrollWidth>innerWidth,frameOverflow:frame.scrollWidth>frame.clientWidth+1};
    });
    assert.deepEqual(report.duplicates,[]);assert.equal(report.menus.length,1);assert(!report.pageOverflow&&!report.frameOverflow,JSON.stringify(report));
  };
  for(const view of ["social","options","stats","equipment","inventory","quest","map","bestiary","achievements"]){await page.evaluate(view=>showView(view,{toggle:false}),view);await audit();if(["social","options","stats","achievements"].includes(view))await capture(view);}
  await page.evaluate(()=>toggleGameMenu(true));
  assert(await page.locator('#game-menu-items button').evaluateAll(nodes=>nodes.every(n=>getComputedStyle(n,'::before').content==='none')));
  await page.evaluate(()=>toggleGameMenu(false));
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>showView("equipment",{toggle:false}));await worn().waitFor();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),"Mobile page must not overflow horizontally");
  await capture("equipment-mobile");
  for(const view of ["social","options","stats","inventory","quest","map","bestiary","achievements"]){await page.evaluate(view=>showView(view,{toggle:false}),view);await audit();if(["inventory","bestiary"].includes(view))await capture(`${view}-mobile`);}
  await page.emulateMedia({reducedMotion:"reduce"});await page.evaluate(()=>showView("equipment",{toggle:false}));assert.equal(await page.locator("#equipment-view .gear-card").first().evaluate(node=>getComputedStyle(node).animationName),"none");
  assert(requests.includes("equip")&&requests.includes("unequip"));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,commands:requests.filter(action=>["equip","unequip"].includes(action)),checks:["swap","reload","set bonuses in three menus","nine menus desktop/mobile","unique IDs","single visible menu","no overflow","bestiary selection","reduced motion"],screenshots:12}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
