"use strict";
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.ui-test/node_modules/jsdom');
function setup(){
 const dom=new JSDOM('<body><section id="battle"></section></body>',{runScripts:'outside-only'}),w=dom.window;
 w.eval('const $=id=>document.getElementById(id);let regionTravelState=null,currentView="map";const session={id:"s"};let closes=0;function toggleGameMenu(){closes++;}'+fs.readFileSync('jeuxRPG/multiplayer/web/app_world.js','utf8')+';toggleGameMenu=()=>{};window.syncRegionTravel=syncRegionTravel;window.renderJourney=renderJourney;');
 return {w,dom};
}
test('physical transitions and transient gaps never open the atlas in the seamless world',()=>{
 const {w}=setup();try{
  w.eval('syncRegionTravel({field_map:"rosee",coaches:{enabled:true}});syncRegionTravel({field_map:null,moving:false,coaches:{enabled:true}})');
  assert(!w.document.body.classList.contains('hud-menu-open'));
  w.eval('syncRegionTravel({field_map:"lisiere",coaches:{enabled:true}})');
  assert(!w.document.body.classList.contains('hud-menu-open'));
 }finally{w.close();}
});
test('coach cinematic and preserved walker toggle cleanly without duplicate actors',()=>{
 const {w}=setup();try{
  w.eval('renderJourney({moving:true,battle:null,world:{routes:[]},transit:{mode:"coach"},travel_progress:.5,travel_remaining_real_seconds:4})');
  assert(w.document.body.classList.contains('journey-active'));
  assert(!w.document.getElementById('journey-coach').hidden);assert(w.document.getElementById('journey-player').hidden);
  assert.equal(w.document.querySelectorAll('#journey-coach [style]').length,0,'SVG markup must obey the desktop style policy');
  w.eval('renderJourney({moving:true,battle:null,world:{routes:[]},transit:{mode:"walk"},travel_progress:.5,travel_remaining_real_seconds:4})');
  assert(w.document.getElementById('journey-coach').hidden);assert(!w.document.getElementById('journey-player').hidden);
  assert.equal(w.document.querySelectorAll('#journey-player svg').length,1);
  w.eval('renderJourney({moving:false,battle:{}})');
  assert(!w.document.body.classList.contains('journey-active'));
 }finally{w.close();}
});
