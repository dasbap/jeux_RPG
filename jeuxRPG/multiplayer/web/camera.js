"use strict";
function adjustFieldCamera(action) {
  if (!session?.tutorial) return;
  if (!session.tutorial.battle) {
    const node = [...$("world-map").children].find(node => node.dataset.map === activeWorldMap) || $("world-map").querySelector("svg");
    if (!node) return;
    const camera = worldCameras.get(node.dataset.map);
    if (action === "in") camera.zoom = Math.min(6, camera.zoom * 1.3);
    else if (action === "out") camera.zoom = Math.max(1, camera.zoom / 1.3);
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

function installWorldCamera(node) {
  const key = node.dataset.map;
  if (!worldCameras.has(key)) {
    const [, , width, height] = node.getAttribute("viewBox").split(" ").map(Number);
    worldCameras.set(key, {width, height, zoom: 1, x: width / 2, y: height / 2});
  }
  const camera = worldCameras.get(key);
  const width = camera.width / camera.zoom, height = camera.height / camera.zoom;
  camera.x = Math.max(width / 2, Math.min(camera.width - width / 2, camera.x));
  camera.y = Math.max(height / 2, Math.min(camera.height - height / 2, camera.y));
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
