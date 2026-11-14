import React, {useEffect,useState} from 'react';
import {invoke,isTauri} from '@tauri-apps/api/core';
type Item={id:string;name:string};
type Task={id:string;short_id:string;title:string};
type Status={connected:boolean;entry:{id:string;task_id:string;start_time:string}|null;activity_score:number|null;screenshots:number;input_available:boolean;paused_for_idle:boolean;idle_gap?:{start_time:string;end_time:string}|null;error:string|null};
const empty:Status={connected:false,entry:null,activity_score:null,screenshots:0,input_available:false,paused_for_idle:false,error:null};
const call=<T,>(command:string,args?:Record<string,unknown>)=>invoke<T>(command,args);
const read=<T,>(path:string)=>call<T>('read_api',{path});
export const App:React.FC=()=>{
 const [status,setStatus]=useState(empty),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [base,setBase]=useState(localStorage.getItem('stride_server')||'http://localhost:8000/api/v1');
 const [email,setEmail]=useState(''),[password,setPassword]=useState('');
 const [orgs,setOrgs]=useState<Item[]>([]),[org,setOrg]=useState('');
 const [projects,setProjects]=useState<Item[]>([]),[project,setProject]=useState('');
 const [tasks,setTasks]=useState<Task[]>([]),[task,setTask]=useState(''),[now,setNow]=useState(Date.now());
 const [prefs,setPrefs]=useState({screenshots_enabled:false,blur:true,randomize:true,screenshot_interval_seconds:600,idle_threshold_seconds:300});
 async function run(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){setError(String(e));}finally{setBusy(false);}}
 useEffect(()=>{if(!isTauri())return;let live=true;const poll=()=>call<Status>('get_daemon_status').then(s=>{if(live)setStatus(s);}).catch(e=>{if(live)setError(String(e));});poll();const timer=setInterval(poll,2000);return()=>{live=false;clearInterval(timer);};},[]);
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
 useEffect(()=>{if(!status.connected)return;let live=true;read<Item[]>('/organizations').then(o=>{if(live)setOrgs(o);}).catch(e=>{if(live)setError(String(e));});return()=>{live=false;};},[status.connected]);
 async function changeOrg(id:string){await run(async()=>{const s=await call<Status>('select_organization',{orgId:id});setStatus(s);setOrg(id);setProject('');setTasks([]);setTask('');const ws=await read<Item[]>(`/organizations/${id}/workspaces`);setProjects((await Promise.all(ws.map(w=>read<Item[]>(`/projects/workspace/${w.id}`)))).flat());});}
 async function changeProject(id:string){await run(async()=>{setProject(id);setTasks([]);setTask('');const items=await read<Task[]>(`/tasks/project/${id}`);setTasks(items);setTask(items[0]?.id||'');});}
 const sec=status.entry?Math.max(0,Math.floor((now-new Date(status.entry.start_time).getTime())/1000)):0;
 const duration=[Math.floor(sec/3600),Math.floor(sec/60)%60,sec%60].map(n=>String(n).padStart(2,'0')).join(':');
 return <main className="min-h-screen bg-slate-950 text-slate-100 p-5 space-y-5"><header><h1 className="font-bold text-xl">Stride Companion</h1><p className="text-xs text-slate-400">Time and activity tracker</p></header>
 {!isTauri()&&<p role="alert" className="text-amber-300">Open the native desktop app to connect and track time.</p>}
 {(error||status.error)&&<p role="alert" className="text-red-300">{error||status.error}</p>}
 {!status.connected?<form className="space-y-4" onSubmit={e=>{e.preventDefault();run(async()=>{setStatus(await call<Status>('connect',{base,email,password}));setPassword('');localStorage.setItem('stride_server',base);});}}>
 <label>Server API URL<input className="field" type="url" required value={base} onChange={e=>setBase(e.target.value)}/></label>
 <label>Email<input className="field" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
 <label>Password<input className="field" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>
 <button className="btn" disabled={busy||!isTauri()}>{busy?'Connecting…':'Sign in'}</button></form>:<>
 <label>Organization<select className="field" value={org} disabled={busy||!!status.entry} onChange={e=>changeOrg(e.target.value)}><option value="" disabled>Select organization</option>{orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
 <label>Project<select className="field" value={project} disabled={busy||!!status.entry} onChange={e=>changeProject(e.target.value)}><option value="" disabled>Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
 <label>Task<select className="field" value={status.entry?.task_id||task} disabled={busy||!!status.entry} onChange={e=>setTask(e.target.value)}><option value="" disabled>Select task</option>{tasks.map(t=><option key={t.id} value={t.id}>{t.short_id}: {t.title}</option>)}</select></label>
 {status.paused_for_idle&&<p role="status" className="text-amber-300">Stopped at your last input. Keep or discard the idle interval before restarting.</p>}
 {status.idle_gap&&<div className="space-y-2"><p>{new Date(status.idle_gap.start_time).toLocaleTimeString()} – {new Date(status.idle_gap.end_time).toLocaleTimeString()}</p><button className="btn" disabled={busy} onClick={()=>run(async()=>setStatus(await call<Status>('resolve_idle',{keep:true})))}>Keep idle time as a draft entry</button><button className="btn" disabled={busy} onClick={()=>run(async()=>setStatus(await call<Status>('resolve_idle',{keep:false})))}>Discard idle time</button></div>}
 <section className="border border-slate-800 rounded-xl p-5 space-y-4 text-center"><p>{status.entry?'Recording session':'Ready to track'}</p><p className="text-4xl font-mono" aria-label="Session duration">{duration}</p><button className="btn" disabled={busy||(!status.entry&&(!org||!task))} onClick={()=>run(async()=>setStatus(status.entry?await call<Status>('stop_tracking'):await call<Status>('start_tracking',{taskId:task})))}>{status.entry?'Stop and save':'Start timer'}</button></section>
 <section className="grid grid-cols-2 gap-3 text-sm"><p>Activity<br/><strong>{status.activity_score===null?'No sample yet':`${status.activity_score}%`}</strong></p><p>Uploads since login<br/><strong>{status.screenshots}</strong></p></section>
 {!status.input_available&&<p className="text-xs text-amber-300">Global input monitoring is unavailable. Grant OS input/accessibility permission or use a supported desktop session. Activity is not estimated.</p>}
 <fieldset disabled={busy||!!status.entry} className="border border-slate-800 p-3 rounded-xl space-y-3"><legend>Capture and privacy</legend>
 <label><input type="checkbox" checked={prefs.screenshots_enabled} onChange={e=>setPrefs({...prefs,screenshots_enabled:e.target.checked})}/> Enable screenshots</label>
 <label><input type="checkbox" checked={prefs.blur} onChange={e=>setPrefs({...prefs,blur:e.target.checked})}/> Blur before upload</label>
 <label><input type="checkbox" checked={prefs.randomize} onChange={e=>setPrefs({...prefs,randomize:e.target.checked})}/> Randomize capture intervals</label>
 <label>Capture interval (minutes)<input className="field" type="number" min={1} max={60} value={prefs.screenshot_interval_seconds/60} onChange={e=>setPrefs({...prefs,screenshot_interval_seconds:Number(e.target.value)*60})}/></label>
 <label>Idle threshold (minutes)<input className="field" type="number" min={1} max={60} value={prefs.idle_threshold_seconds/60} onChange={e=>setPrefs({...prefs,idle_threshold_seconds:Number(e.target.value)*60})}/></label>
 <button className="btn" onClick={()=>run(()=>call('configure_tracking',{preferences:prefs}))}>Apply settings</button></fieldset>
 <p className="text-xs text-slate-400">Only input counts and mouse distance are uploaded. Key contents and window titles are never uploaded. Closing the window keeps tracking in the tray.</p>
 <button className="btn" disabled={busy} onClick={()=>run(async()=>{await call('disconnect');setStatus(empty);setOrg('');setProject('');})}>Stop and disconnect</button>
 </>}</main>;
};
