"use strict";
(() => {
  const bridge=globalThis.rpgNativeApi;
  if(!bridge) return;
  const originalFetch=globalThis.fetch.bind(globalThis),pending=new Map();
  let sequence=0;
  bridge.onmessage=event=>{
    const result=JSON.parse(event.data),task=pending.get(result.id);
    if(!task)return;
    pending.delete(result.id);task.cleanup();task.resolve(result);
  };
  globalThis.fetch=async(input,options={})=>{
    const request=new Request(input,options),url=new URL(request.url);
    if(url.origin!==location.origin||!url.pathname.startsWith("/api/")||url.pathname==="/api/classes")return originalFetch(input,options);
    if(request.signal.aborted)throw new DOMException("Requête annulée","AbortError");
    const id=++sequence,body=request.method==="GET"?null:await request.text();
    const result=await new Promise((resolve,reject)=>{
      const abort=()=>{pending.delete(id);reject(new DOMException("Requête annulée","AbortError"));};
      pending.set(id,{resolve,cleanup:()=>request.signal.removeEventListener("abort",abort)});
      request.signal.addEventListener("abort",abort,{once:true});
      bridge.postMessage(JSON.stringify({type:"api",id,path:url.pathname+url.search,method:request.method,headers:Object.fromEntries(request.headers),body}));
    });
    return new Response(result.body,{status:result.status,headers:result.headers});
  };
  const flush=async()=>{if(typeof soloTransport!=="undefined"&&soloTransport)await soloTransport.flush();};
  globalThis.rpgMobile={flush,exit:async()=>{
    const dialog=document.querySelector("dialog[open]");
    if(dialog){const event=new Event("cancel",{cancelable:true});if(dialog.dispatchEvent(event))dialog.close();return;}
    if(document.body.classList.contains("hud-menu-open")){document.getElementById("back-view").click();return;}
    try{await flush();}finally{bridge.postMessage(JSON.stringify({type:"finish"}));}
  }};
  document.addEventListener("visibilitychange",()=>{if(document.hidden)flush().catch(()=>{});});
})();
