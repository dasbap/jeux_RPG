"use strict";
function adjustFieldCamera(action) {
  if (!session?.tutorial) return;
  if (!session.tutorial.battle) {
    const node = [...$("world-map").children].find(node => node.dataset.map === activeWorldMap) || $("world-map").querySelector("svg");
    if (!node) return;
    const camera = worldCameras.get(node.dataset.map);
    if (action === "in") camera.zoom = Math.min(6, camera.zoom * 1.3);
    else if (action === "out") camera.zoom = Math.max(.45, camera.zoom / 1.3);
    else if (action === "center") { camera.zoom = 1; camera.x = camera.width / 2; camera.y = camera.height / 2; }
    else { camera.x += action === "left" ? -camera.width / camera.zoom / 5 : action === "right" ? camera.width / camera.zoom / 5 : 0; camera.y += action === "up" ? -camera.height / camera.zoom / 5 : action === "down" ? camera.height / camera.zoom / 5 : 0; }
    installWorldCamera(node);
    return;
  }
  if (!fieldCamera) return;
  if (action === "in") fieldCamera.span = Math.max(4, fieldCamera.span - 4);
  else if (action === "out") fieldCamera.span = Math.min(64, fieldCamera.span + 4);
  else if (action === "center") fieldCamera.follow = true;
  else { fieldCamera.follow = false; fieldCamera.x += action === "left" ? -5 : action === "right" ? 5 : 0; fieldCamera.y += action === "up" ? -5 : action === "down" ? 5 : 0; }
  const map = session.tutorial.battle.map;
  fieldCamera.x = Math.max(0, Math.min(map.width - 1, fieldCamera.x));
  fieldCamera.y = Math.max(0, Math.min(map.height - 1, fieldCamera.y));
  renderTutorial(session.tutorial);
}
for (const action of ["in", "out", "center"]) $(`field-${["in", "out"].includes(action) ? "zoom-" : ""}${action}`).addEventListener("click", () => adjustFieldCamera(action));

function installWorldCamera(node) {
  const key = node.dataset.map;
  if (!worldCameras.has(key)) {
    const [, , width, height] = node.getAttribute("viewBox").split(" ").map(Number);
    worldCameras.set(key, {width, height, zoom: 1, x: width / 2, y: height / 2});
  }
  const camera = worldCameras.get(key);
  const width = camera.width / camera.zoom, height = camera.height / camera.zoom;
  if (width >= camera.width) camera.x = camera.width / 2;
  else camera.x = Math.max(width / 2, Math.min(camera.width - width / 2, camera.x));
  if (height >= camera.height) camera.y = camera.height / 2;
  else camera.y = Math.max(height / 2, Math.min(camera.height - height / 2, camera.y));
  node.setAttribute("viewBox", `${camera.x - width / 2} ${camera.y - height / 2} ${width} ${height}`);
  node.onclick = () => { activeWorldMap = key; };
  node.onwheel = event => { event.preventDefault(); activeWorldMap = key; adjustFieldCamera(event.deltaY > 0 ? "out" : "in"); };
}

function returnCameraToPlayer() {
  clearTimeout(cameraReturnTimer);
  cameraReturnTimer = null;
  if (fieldCamera && session?.tutorial?.battle?.map.id === fieldCamera.map) {
    fieldCamera.follow = true;
    renderTutorial(session.tutorial);
  }
}
const cameraSurface = $("world-map");
cameraSurface.addEventListener("pointerdown", event => {
  if (!event.isPrimary || event.button !== 0 || cameraDrag || !session?.tutorial?.battle || !fieldCamera) return;
  const node = cameraSurface.querySelector(".battle-map");
  if (!node) return;
  const view = node.viewBox.baseVal, bounds = node.getBoundingClientRect();
  cameraDrag = {pointer: event.pointerId, map: fieldCamera.map, startX: event.clientX, startY: event.clientY, x: fieldCamera.x, y: fieldCamera.y, scaleX: view.width / bounds.width / 40, scaleY: view.height / bounds.height / 40, moved: false};
});
cameraSurface.addEventListener("pointermove", event => {
  const drag = cameraDrag;
  if (!drag || event.pointerId !== drag.pointer) return;
  if (fieldCamera?.map !== drag.map || session?.tutorial?.battle?.map.id !== drag.map) { cameraDrag = null; return; }
  const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
  if (!drag.moved && Math.hypot(dx, dy) < 6) return;
  if (!drag.moved) { clearTimeout(cameraReturnTimer); cameraReturnTimer = null; drag.moved = true; cameraSurface.setPointerCapture(event.pointerId); }
  event.preventDefault();
  fieldCamera.follow = false;
  const map = session.tutorial.battle.map;
  fieldCamera.x = Math.max(0, Math.min(map.width - 1, drag.x - dx * drag.scaleX));
  fieldCamera.y = Math.max(0, Math.min(map.height - 1, drag.y - dy * drag.scaleY));
  suppressMapClickUntil = Date.now() + 500;
  if (cameraFrame === null) cameraFrame = requestAnimationFrame(() => {
    cameraFrame = null;
    if (session?.tutorial?.battle?.map.id === drag.map && fieldCamera?.map === drag.map) renderBattle(session.tutorial, session.tutorial.players.find(player => player.id === session.me));
  });
});
function releaseCamera(event) {
  const drag = cameraDrag;
  if (!drag || event && event.pointerId !== drag.pointer) return;
  cameraDrag = null;
  if (drag.moved) {
    suppressMapClickUntil = Date.now() + 500;
    cameraReturnTimer = setTimeout(() => {
      if (fieldCamera?.map === drag.map) returnCameraToPlayer();
    }, 2000);
  }
}
for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) cameraSurface.addEventListener(name, releaseCamera);
for (const name of ["click", "dblclick"]) cameraSurface.addEventListener(name, event => {
  if (Date.now() < suppressMapClickUntil) { event.preventDefault(); event.stopImmediatePropagation(); }
}, true);
window.addEventListener("blur", () => releaseCamera());
window.addEventListener("resize", () => { if (session?.tutorial?.battle) renderTutorial(session.tutorial); });
