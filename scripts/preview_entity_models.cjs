const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'.data/browser-binaries');
const {chromium}=require('../.data/browser-tools/node_modules/playwright');
(async()=>{
 const content=JSON.parse(fs.readFileSync(path.join(root,'projects/authored/content.json'),'utf8')).content;
 const mobs=JSON.parse(fs.readFileSync(path.join(root,'projects/authored/mobs.json'),'utf8')).maps;
 const converted=process.argv.includes('--converted');
 const models={};
 if(converted)for(const target of Object.keys(content.sprites.bindings)){
  if(!target.startsWith('mob:'))continue;
  const file=fs.readFileSync(path.join(root,'dist/models_3d',target.replace(':','_')+'_0.glb'));
  const size=file.readUInt32LE(12),data=JSON.parse(file.subarray(20,20+size).toString()),base=28+size;
  const attribute=index=>{const a=data.accessors[index],v=data.bufferViews[a.bufferView];return Array.from(new Float32Array(file.buffer,file.byteOffset+base+(v.byteOffset||0),a.count*3));};
  const a=data.accessors[3],v=data.bufferViews[a.bufferView];
  models[target]={positions:attribute(0),colors:attribute(2),indices:Array.from(new Uint32Array(file.buffer,file.byteOffset+base+v.byteOffset,a.count))};
 }
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1200,height:900}});
  await page.route('**/*',route=>route.abort());
  await page.setContent('<style>body{background:#15212b;color:#ebecdf;font:14px system-ui;margin:20px}.grid{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}article{background:#25353c;border:1px solid #607074;border-radius:8px;text-align:center;padding:8px}img{width:110px;height:120px}small{display:block;color:#b4cbbe}</style><h2>Entités : silhouettes et équipements 3D</h2><div class="grid"></div>');
  await page.addScriptTag({content:fs.readFileSync(path.join(root,'jeuxRPG/multiplayer/web/scene_3d.js'),'utf8')});
  await page.evaluate(({catalog,mobs,models,converted})=>{
   const canvas=document.createElement('canvas');canvas.width=220;canvas.height=240;
   const gl=canvas.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true});
   if(!gl)throw Error('WebGL unavailable');
   const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
   const program=gl.createProgram();
   gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 p;attribute vec3 c;varying vec3 color;void main(){gl_Position=vec4(p.x*1.3,(p.y*.85-p.z*.4)-.65,-(p.z+p.y*.4)*.2,1.0);color=c;}'));
   gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 color;void main(){gl_FragColor=vec4(color,1.0);}'));
   gl.linkProgram(program);gl.useProgram(program);gl.enable(gl.DEPTH_TEST);gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());
   for(const [name,offset] of [['p',0],['c',12]]){const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,3,gl.FLOAT,false,24,offset);}
   for(const [key,id] of Object.entries(catalog.bindings)){
    if(!key.startsWith('mob:'))continue;
    const mesh=new RPGScene3D.Mesh();RPGScene3D.model(mesh,{position:[0,0],look:{id,weapon:catalog.equipment?.[key]||'',color:catalog.colors?.[key]||catalog.assets[id].palette[3]},phase:0,unit:{},yaw:-.3},0);
    if(converted){
     const model=models[key];mesh.data=[];
     for(const index of model.indices){const i=index*3,px=model.positions[i]*1.3,pz=model.positions[i+2]*1.3;
      const color=model.colors.slice(i,i+3).map(v=>v<=.0031308?v*12.92:1.055*v**(1/2.4)-.055);
      mesh.data.push(px*.88+pz*.48,model.positions[i+1]*1.3,pz*.88-px*.48,...color);
     }
    }
    gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(mesh.data),gl.STATIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,mesh.data.length/6);
    if(gl.getError()!==gl.NO_ERROR)throw Error('Invalid mesh '+key);
    const card=document.createElement('article'),img=document.createElement('img'),title=document.createElement('div'),note=document.createElement('small');img.src=canvas.toDataURL();title.textContent=mobs[key.slice(4)].name;note.textContent=(catalog.equipment?.[key]||'Sans arme').replace('arme_','');card.append(img,title,note);document.querySelector('.grid').append(card);
   }
  },{catalog:content.sprites,mobs,models,converted});
  await page.screenshot({path:path.join(root,converted?'.data/converted-models.png':'.data/entity-models.png'),fullPage:true});
  console.log('58 modèles rendus sans erreur WebGL : .data/entity-models.png');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
