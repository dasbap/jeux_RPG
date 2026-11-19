"use strict";
const assert=require("node:assert/strict");
const readline=require("node:readline");
const {chromium}=require("../.data/browser-tools/node_modules/playwright");
const input=readline.createInterface({input:process.stdin})[Symbol.asyncIterator]();
const receive=async()=>JSON.parse((await input.next()).value);
const emit=value=>process.stdout.write(JSON.stringify(value)+"\n");
(async()=>{
  const config=await receive(),browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:960},serviceWorkers:"block"});
    const errors=[],external=[];page.on("pageerror",error=>errors.push(error.message));
    await page.route("**/*",route=>{const url=new URL(route.request().url());if(url.origin===config.url)return route.continue();external.push(url.origin);return route.abort();});
    await page.goto(config.url);
    await page.locator("#registration details summary").click();
    await page.locator("#login-name").fill("WorldLocalTest");await page.locator("#login-password").fill(config.password);
    await page.locator('#restore-form button[type="submit"]').click();await page.locator("#character-list button").first().click();
    await page.waitForFunction(()=>session?.tutorial?.living_world.nearby.filter(actor=>actor.kind==="guards").length===3);
    await page.waitForFunction(()=>session.tutorial.mobs[0].stats.hp.current<100);
    assert.equal(await page.evaluate(()=>session.tutorial.living_world.nearby.find(actor=>actor.kind==="guards").mode),"combat");
    await page.waitForFunction(()=>document.querySelector(".rpg-canvas3d")?.scene3D.stats.frames>2);
    const guards=await page.evaluate(()=>document.querySelector(".rpg-canvas3d").scene3D.items.filter(a=>a.unit?.kind==="guards").map(a=>a.look.weapon));
    assert.equal(guards.filter(w=>w==="arme_bow").length,1);
    assert.equal(guards.filter(w=>w==="arme_sword_shield").length,2);
    if(config.town==="rosee") {
      assert.equal(await page.evaluate(()=>session.tutorial.battle.map.width),88);
      assert.equal(await page.evaluate(()=>session.tutorial.battle.map.height),56);
      assert(await page.evaluate(()=>session.tutorial.battle.map.exits.some(exit=>exit.destination==="rosee_caserne")));
      const overview=await page.evaluate(()=>renderStaticMap(session.tutorial.battle.map).outerHTML);
      await page.screenshot({path:".data/rosee-expanded-game.png",fullPage:true});
      const preview=await browser.newPage({viewport:{width:1320,height:920}});
      await preview.setContent(`<html><head><style>body{margin:0;background:#101923}svg{width:100%;height:920px}.battle-cell{fill:#667356;stroke:#728064}.terrain-path{fill:#9b8764}.battle-cover{fill:#4a4e57}.battle-exit{fill:#d6c789}</style></head><body>${overview}</body></html>`);
      await preview.screenshot({path:".data/rosee-expanded-overview.png"});await preview.close();
      emit({check:"Expanded Rosée renders with gates, barracks access, one bow and two sword/shield guards",result:"passed"});
    }
    emit({check:"Three guards autonomously attack a real hostile mob; HP bars render",result:"passed"});
    emit({guard_action:"wound"});await receive();await page.evaluate(()=>refresh(true));
    await page.waitForFunction(()=>{const guards=session.tutorial.living_world.nearby.filter(actor=>actor.kind==="guards");return guards.length===3&&guards.every(actor=>actor.mode==="retreat");});
    await page.screenshot({path:".data/guard-patrol-retreat.png",fullPage:true});
    emit({guard_action:"safe"});await receive();await page.evaluate(()=>refresh(true));
    await page.waitForFunction(()=>{const guards=session.tutorial.living_world.nearby.filter(actor=>actor.kind==="guards");return guards.length===3&&guards.every(actor=>actor.mode==="recover");});
    emit({guard_action:"recover"});await receive();await page.evaluate(()=>refresh(true));
    await page.waitForFunction(()=>{const guards=session.tutorial.living_world.nearby.filter(actor=>actor.kind==="guards");return guards.length===3&&guards.every(actor=>actor.mode==="patrol"&&actor.hp>=actor.max_hp*.8);});
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    emit({check:"One wounded soldier triggers collective retreat; safe recovery and return to patrol; no external requests",result:"passed"});
  }finally{await browser.close();}
})().then(()=>process.exit(0),error=>{process.stderr.write(error.stack+"\n");process.exit(1);});
