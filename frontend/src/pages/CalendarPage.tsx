import React,{useEffect,useState} from 'react';
import {CalendarView,Project} from '../types';
import {api} from '../services/api';
type Mode='month'|'week'|'multiweek'|'day';
const iso=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export const CalendarPage:React.FC<{project:Project;onSelectTask?:(id:string)=>void}>=({project,onSelectTask})=>{
 const [feed,setFeed]=useState('');
 const [anchor,setAnchor]=useState(new Date()),[mode,setMode]=useState<Mode>('month');
 const [calendar,setCalendar]=useState<CalendarView|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const month=anchor.getMonth()+1,year=anchor.getFullYear();
 const load=()=>api.getCalendar(project.id,mode==='month'?month:undefined,mode==='month'?year:undefined);
 useEffect(()=>{let live=true;setError('');load().then(c=>{if(live)setCalendar(c);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[project.id,month,year,mode]);
 const start=new Date(anchor);start.setHours(0,0,0,0);
 let count=1;
 if(mode==='month'){start.setDate(1);start.setDate(1-start.getDay());count=42;}
 else if(mode!=='day'){start.setDate(start.getDate()-start.getDay());count=mode==='week'?7:21;}
 const days=Array.from({length:count},(_,i)=>{const d=new Date(start);d.setDate(start.getDate()+i);return d;});
 function navigate(delta:number){const next=new Date(anchor);if(mode==='month'){next.setDate(1);next.setMonth(next.getMonth()+delta);}else next.setDate(next.getDate()+delta*(mode==='day'?1:mode==='week'?7:21));setAnchor(next);}
 async function reschedule(id:string,date:string){setBusy(true);setError('');try{await api.updateTask(id,{due_date:date});setCalendar(await load());}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <section className="flex-1 p-6 overflow-auto space-y-4">
 <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-lg font-bold">Project Calendar</h1><div className="flex flex-wrap gap-2"><label className="label">View<select aria-label="Calendar view" className="field" value={mode} onChange={e=>setMode(e.target.value as Mode)}><option value="month">Month</option><option value="week">Week</option><option value="multiweek">Three weeks</option><option value="day">Day</option></select></label><button className="btn" onClick={async()=>{try{const url=URL.createObjectURL(await api.calendarExport(project.id));const a=document.createElement('a');a.href=url;a.download='stride-calendar.ics';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError((e as Error).message);}}}>Export calendar</button></div></div>
 {error&&<p role="alert" className="error">{error}</p>}
 <div className="flex gap-2 flex-wrap"><button className="btn" onClick={async()=>{try{setFeed((await api.calendarFeed(project.id)).url);}catch(e){setError((e as Error).message);}}}>Create external calendar link</button><button className="btn" onClick={async()=>{try{await api.revokeCalendarFeed(project.id);setFeed('');}catch(e){setError((e as Error).message);}}}>Revoke calendar link</button></div>{feed&&<label className="label">Private subscription URL (expires after 30 days)<input className="field" readOnly value={feed} onFocus={e=>e.currentTarget.select()}/><span className="text-xs text-slate-400">Add this URL in Google Calendar or any iCalendar client. Anyone with this link can read the project calendar until it expires or you revoke it.</span></label>}
 <nav className="flex items-center gap-3"><button className="btn" aria-label={mode==='month'?'Previous month':'Previous period'} onClick={()=>navigate(-1)}>Previous</button><span>{mode==='month'?anchor.toLocaleDateString(undefined,{month:'long',year:'numeric'}):`${days[0].toLocaleDateString()} – ${days[days.length-1].toLocaleDateString()}`}</span><button className="btn" aria-label={mode==='month'?'Next month':'Next period'} onClick={()=>navigate(1)}>Next</button><button className="btn" onClick={()=>setAnchor(new Date())}>Today</button></nav>
 <div className={`grid gap-2 ${mode==='day'?'grid-cols-1':'grid-cols-7 min-w-[700px]'}`}>{days.map(day=>{const key=iso(day);const events=calendar?.events.filter(e=>e.due_date===key)||[];return <article key={key} data-date={key} className={`border rounded-xl p-2 min-h-32 ${day.getMonth()===anchor.getMonth()?'border-slate-800 bg-slate-900/40':'border-slate-900 text-slate-500'}`} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const id=e.dataTransfer.getData('text/plain');if(id&&!busy)reschedule(id,key);}}><h2 className="text-xs mb-3">{day.toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short'})}</h2>{events.map(event=><button key={event.id} draggable={!busy} onDragStart={e=>e.dataTransfer.setData('text/plain',event.id)} className="block w-full text-left p-2 mb-2 bg-slate-800 rounded text-xs" onClick={()=>onSelectTask?.(event.id)}><span className="text-sky-400">{event.short_id}</span><span className="float-right w-2 h-2 rounded-full" style={{backgroundColor:event.status_color}}/><p>{event.title}</p></button>)}</article>;})}</div></section>;
};
