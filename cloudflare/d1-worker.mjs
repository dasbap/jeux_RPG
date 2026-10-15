const TABLES = ["meta","accounts","players","account_characters","account_sessions","friendships","teams","team_members","team_invites","guilds","guild_members","guild_invites","account_status","sessions","members","tutorials","events","receipts","receipt_expiry","admin_audit"];
const KEYS = {"meta":["key"],"accounts":["id"],"players":["id"],"account_characters":["account_id","class_name"],"account_sessions":["token_hash"],"friendships":["first_id","second_id"],"teams":["id"],"team_members":["account_id"],"team_invites":["id"],"guilds":["id"],"guild_members":["account_id"],"guild_invites":["id"],"account_status":["player_id"],"sessions":["id"],"members":["session_id","player_id"],"tutorials":["session_id"],"events":["id"],"receipts":["player_id","request_id"],"receipt_expiry":["player_id","request_id"],"admin_audit":["id"]};
const headers = {"content-type":"application/json","cache-control":"no-store"};
const reply = (body,status=200) => new Response(JSON.stringify(body),{status,headers});
const validFence = value => Number.isSafeInteger(value) && value >= 0;
const identifier = name => /^[a-z][a-z0-9_]*$/.test(name);
function authorize(request,env) {
  const expected = env.RPG_D1_SERVICE_TOKEN;
  const supplied = request.headers.get("authorization");
  if (!expected || expected.length < 32 || !supplied || !supplied.startsWith("Bearer ")) return false;
  const actual = supplied.slice(7);
  const a = new TextEncoder().encode(actual);
  const b = new TextEncoder().encode(expected);
  let mismatch = a.length ^ b.length;
  for(let i=0;i<Math.max(a.length,b.length);i++) mismatch |= (a[i] || 0) ^ (b[i] || 0);
  return mismatch === 0;
}
function guardedFence(db, fence) {
  return db.prepare("INSERT INTO meta(key,value) VALUES('runtime_fence',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").bind(String(fence));
}
function checkpointStatements(db, body) {
  if (!validFence(body.fence) || !Array.isArray(body.changes) || body.changes.length > 1000) throw new Error("invalid_checkpoint");
  const statements=[guardedFence(db,body.fence)];
  for(const item of body.changes) {
    if(!item || !TABLES.includes(item.table) || item.table==="meta" && item.row?.key==="runtime_fence") throw new Error("invalid_table");
    const keys=KEYS[item.table];
    if(!Array.isArray(item.key) || item.key.length!==keys.length) throw new Error("invalid_key");
    if(item.row===null){
      statements.push(db.prepare("DELETE FROM "+item.table+" WHERE "+keys.map(k=>k+"=?").join(" AND ")).bind(...item.key));
      continue;
    }
    if(!item.row || typeof item.row!=="object" || Array.isArray(item.row)) throw new Error("invalid_row");
    const columns=Object.keys(item.row);
    if(!columns.length || columns.length>80 || !columns.every(identifier) || !keys.every(k=>Object.hasOwn(item.row,k))) throw new Error("invalid_columns");
    if(!keys.every((k,i)=>item.row[k]===item.key[i])) throw new Error("mismatched_key");
    const values=columns.map(k=>item.row[k]);
    if(values.some(v=>v!==null && !["number","string","boolean"].includes(typeof v))) throw new Error("invalid_value");
    const updates=columns.filter(k=>!keys.includes(k)).map(k=>k+"=excluded."+k);
    const conflict=updates.length?" DO UPDATE SET "+updates.join(","):" DO NOTHING";
    statements.push(db.prepare("INSERT INTO "+item.table+" ("+columns.join(",")+") VALUES ("+columns.map(()=>"?").join(",")+") ON CONFLICT("+keys.join(",")+")"+conflict).bind(...values));
  }
  return statements;
}
export default {
 async fetch(request,env) {
  if(!authorize(request,env)) return reply({error:"unauthorized"},401);
  if(request.method!=="POST") return reply({error:"method_not_allowed"},405);
  const size=Number(request.headers.get("content-length") || 0);
  if(size>2000000) return reply({error:"too_large"},413);
  let body;
  try { const raw=await request.text(); if(raw.length>2000000) return reply({error:"too_large"},413); body=JSON.parse(raw); } catch {return reply({error:"invalid_json"},400);}
  try {
   if(body.operation==="health") {
    const row=await env.DB.prepare("SELECT version FROM schema_version WHERE id=1").first();
    return reply({ok:true,version:row?.version});
   }
   if(body.operation==="load_snapshot"){
    if(!validFence(body.fence)) return reply({error:"invalid_fence"},400);
    const session=env.DB.withSession("first-primary");
    const batch=await session.batch([guardedFence(session,body.fence),...TABLES.map(t=>session.prepare("SELECT * FROM "+t))]);
    const data=Object.fromEntries(TABLES.map((t,i)=>[t,batch[i+1].results]));
    return reply({data});
   }
   if(body.operation==="persist_checkpoint"){
    const statements=checkpointStatements(env.DB,body);
    await env.DB.batch(statements);
    return reply({ok:true});
   }
   return reply({error:"unknown_operation"},400);
  } catch(error) {
   return reply({error:String(error?.message || "").includes("stale_runtime_fence") ? "stale_runtime_fence" : "database_operation_failed"},409);
  }
 }
};
