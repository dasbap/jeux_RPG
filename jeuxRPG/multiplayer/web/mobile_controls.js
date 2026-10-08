"use strict";
globalThis.createRpgTouchControls = api => {
  const panel = document.createElement("section");
  panel.id = "touch-controls";
  panel.setAttribute("aria-label", "Commandes tactiles");
  const stick = document.createElement("div");
  stick.id = "touch-stick";
  stick.tabIndex = 0;
  stick.setAttribute("role", "application");
  stick.setAttribute("aria-label", "Joystick de déplacement. Glissez ou utilisez les flèches pour marcher, relâchez pour arrêter.");
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  for (const radius of [46, 19]) {
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("cx", "50"); circle.setAttribute("cy", "50"); circle.setAttribute("r", radius);
    svg.append(circle);
  }
  const thumb = svg.lastElementChild;
  stick.append(svg);
  const actions = document.createElement("div");
  actions.id = "touch-actions";
  panel.append(stick, actions);
  document.getElementById("battle").append(panel);
  let pointer = null, vector = [0,0], timer = null, last = -Infinity, pendingStop = false, key = null, direction = null, origin = null;
  function reset() {thumb.setAttribute("cx", "50"); thumb.setAttribute("cy", "50"); vector = [0,0];}
  function halt() {if (timer !== null) clearInterval(timer); timer = null; pointer = null; pendingStop = false; direction = null; origin = null; reset();}
  function tick() {
    const state = api.state();
    if (!state.active || state.key !== key) return halt();
    if (state.busy || Date.now() - last < 250) return;
    if (pendingStop) {
      pendingStop = false;
      if (direction !== null || state.actor?.route?.length) {last = Date.now(); api.stop();}
      return halt();
    }
    if (!vector.some(Boolean)) return;
    const next = vector.map(x => Math.round(x));
    if (!next.some(Boolean)) return;
    if (direction?.join() === next.join() && state.actor?.route?.length) return;
    const currentOrigin = state.actor?.position?.join();
    if (currentOrigin !== undefined && direction?.join() === next.join() && origin === currentOrigin) return;
    last = Date.now();
    if (api.move(next)) {direction = next; origin = currentOrigin;}
  }
  function position(event) {
    const rect = stick.getBoundingClientRect();
    const dx = (event.clientX - rect.left - rect.width/2)/(rect.width/2), dy = (event.clientY - rect.top - rect.height/2)/(rect.height/2);
    const length = Math.hypot(dx,dy), scale = Math.max(1,length);
    vector = length < .2 ? [0,0] : [dx/scale,dy/scale];
    thumb.setAttribute("cx", 50 + vector[0]*28); thumb.setAttribute("cy", 50 + vector[1]*28);
  }
  function release(event) {
    if (event && event.pointerId !== pointer) return;
    pointer = null; reset(); pendingStop = true;
    tick();
  }
  const keys = new Map();
  const arrows = {ArrowUp: [0,-1], ArrowDown: [0,1], ArrowLeft: [-1,0], ArrowRight: [1,0]};
  stick.addEventListener("keydown", event => {
    if (!arrows[event.key] || !api.state().active) return;
    event.preventDefault();
    keys.set(event.key, arrows[event.key]);
    key = api.state().key; pendingStop = false;
    vector = [...keys.values()].reduce((sum, next) => sum.map((v,i) => Math.max(-1, Math.min(1, v + next[i]))), [0,0]);
    if (timer === null) timer = setInterval(tick, 100);
    tick();
  });
  stick.addEventListener("keyup", event => {
    if (!arrows[event.key]) return;
    event.preventDefault(); keys.delete(event.key);
    if (!keys.size) release();
    else vector = [...keys.values()].reduce((sum, next) => sum.map((v,i) => Math.max(-1, Math.min(1, v + next[i]))), [0,0]);
  });
  stick.addEventListener("blur", () => { if (keys.size) { keys.clear(); release(); } });
  stick.addEventListener("pointerdown", event => {
    if (pointer !== null || !api.state().active) return;
    event.preventDefault(); pointer = event.pointerId; key = api.state().key; pendingStop = false;
    stick.setPointerCapture?.(pointer); position(event);
    if (timer === null) timer = setInterval(tick, 100);
    tick();
  });
  stick.addEventListener("pointermove", event => {if (event.pointerId === pointer) {event.preventDefault(); position(event);}});
  for (const name of ["pointerup","pointercancel","lostpointercapture"]) stick.addEventListener(name, release);
  window.addEventListener("blur", () => {if (pointer !== null || keys.size) { keys.clear(); release(); }});
  document.addEventListener("visibilitychange", () => {if (document.hidden && (pointer !== null || keys.size)) release();});
  return {sync() {
    const state = api.state();
    panel.hidden = !state.active;
    if (!state.active || key !== null && state.key !== key) halt();
    const buttons = api.actions();
    while (actions.children.length > buttons.length) actions.lastElementChild.remove();
    buttons.forEach((source, i) => {
      let button = actions.children[i];
      if (!button) {button = document.createElement("button"); actions.append(button);}
      button.textContent = source.textContent.split(" · ")[0];
      button.setAttribute("aria-label", source.textContent);
      button.disabled = state.busy || source.disabled;
      button.onclick = () => {const current = api.actions()[i]; if (!api.state().busy && current && !current.disabled) current.click();};
    });
  }};
};
