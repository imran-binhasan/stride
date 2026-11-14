import { FormEvent, useEffect, useState } from 'react';
import { X, Play, Square, Trash2, Paperclip, ExternalLink } from 'lucide-react';
import { ActiveTimer, ChecklistItem, FigmaLink, OrgMember, Project, Task, TaskPriority, WorkflowStatus } from '../types';
import { useRealtime } from '../hooks/useRealtime';
import { api } from '../services/api';

interface Props {
  task: Task | null; statuses: WorkflowStatus[]; onClose: () => void;
  onUpdate: () => void; activeTimer: ActiveTimer | null; onTimerChange: () => void;
  project?: Project; members?: OrgMember[]; canEdit?: boolean; canDelete?: boolean;
}
export function TaskDrawer({task, statuses, onClose, onUpdate, activeTimer, onTimerChange, project, members = [], canEdit = true, canDelete = false}: Props) {
  const [viewers,setViewers]=useState<Record<string,{name:string;seen:number}>>({});
  const {broadcast:presence,connected:presenceConnected}=useRealtime(task&&api.getOrgId()?`room:org:${api.getOrgId()}:task:${task.id}`:null,msg=>{
    if(msg.event==='USER_PRESENCE' && typeof msg.data.user_id==='string'){
      const id=msg.data.user_id;
      setViewers(old=>{const next={...old};if(msg.data.state==='away')delete next[id];else next[id]={name:String(msg.data.full_name || 'Team member'),seen:Date.now()};return next;});
    }
  });
  useEffect(()=>{
    setViewers({});if(!task||!presenceConnected)return;
    const announce=()=>presence('USER_PRESENCE',{state:'viewing'});announce();
    const timer=setInterval(()=>{announce();setViewers(old=>Object.fromEntries(Object.entries(old).filter(([,viewer])=>Date.now()-viewer.seen<45000)));},15000);
    return()=>{clearInterval(timer);presence('USER_PRESENCE',{state:'away'});};
  },[task?.id,presenceConnected,presence]);
  const [candidates, setCandidates] = useState<Task[]>([]);
  const [draft, setDraft] = useState<Partial<Task>>({});
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [figma, setFigma] = useState<FigmaLink[]>([]);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [downloadUrls, setDownloadUrls] = useState<Record<string,string>>({});
  useEffect(() => {
    if (!task) return;
    setDraft({...task}); setError(''); setConfirmDelete(false);
    const close = (event: KeyboardEvent) => { if(event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [task?.id]);
  useEffect(() => {
    if (!task) return;
    let live = true;
    api.getTable(task.project_id, {limit:"200"}).then(r=>{if(live)setCandidates(r.items.filter(t=>t.id!==task.id));}).catch(e=>{if(live)setError(e.message);});
    api.getChecklist(task.id).then(data => {if(live) setChecklist(data);}).catch(e=>{if(live) setError(e.message);});
    api.listFigmaLinks(task.id).then(data => {if(live) setFigma(data);}).catch(e=>{if(live) setError(e.message);});
    Promise.all((task.attachments || []).map(async attachment => [attachment.id, (await api.attachmentUrl(task.id, attachment.id)).download_url] as const)).then(values=>{if(live) setDownloadUrls(Object.fromEntries(values));}).catch(e=>{if(live) setError(e.message);});
    return () => {live=false;};
  }, [task]);
  if (!task) return null;
  async function run(action: () => Promise<unknown>) {
    setError(''); setBusy(true);
    try {await action(); await onUpdate(); if(task) setChecklist(await api.getChecklist(task.id));}
    catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  const value = (field: keyof Task, v: unknown) => setDraft(prev=>({...prev,[field]:v}));
  const active = activeTimer?.task_id === task.id;
  function submit(e: FormEvent<HTMLFormElement>, action: (values: FormData) => Promise<unknown>) {
    e.preventDefault(); const form=e.currentTarget; const values=new FormData(form);
    run(async()=>{await action(values); form.reset();});
  }
  return <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end" onMouseDown={e=>{if(e.target===e.currentTarget) onClose();}}>
    <section role="dialog" aria-modal="true" aria-labelledby="task-heading" className="w-full max-w-2xl h-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
      <header className="flex justify-between items-center gap-3 border-b border-slate-800 p-4"><span className="font-mono text-sm text-sky-400">{task.short_id}</span><div className="flex gap-2"><button disabled={busy} className="btn" onClick={()=>run(async()=>{if(active) await api.stopTimer(); else await api.startTimer(task.id); onTimerChange();})}>{active ? <Square size={14}/> : <Play size={14}/>} {active?'Stop timer':'Track time'}</button><button className="btn" aria-label="Close task" onClick={onClose}><X size={18}/></button></div></header>
      <div className="overflow-auto flex-1 p-5 space-y-6">
        {Object.keys(viewers).length>0&&<p className="text-xs text-sky-400" role="status">Also viewing: {Object.values(viewers).map(v=>v.name).join(", ")}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <form className="space-y-4" onSubmit={e=>{e.preventDefault(); run(()=>api.updateTask(task.id, {title:draft.title,type:draft.type,description:draft.description,priority:draft.priority,status_id:draft.status_id,assignee_id:draft.assignee_id || null,sprint_id:draft.sprint_id || null,story_points:draft.story_points ?? null,estimated_hours:draft.estimated_hours ?? null,start_date:draft.start_date || null,due_date:draft.due_date || null,recurrence:draft.recurrence || null}));}}>
          <h1 id="task-heading" className="text-lg font-semibold">{task.title}</h1>
          <label className="label">Title<input autoFocus className="field" required maxLength={255} disabled={!canEdit} value={draft.title || ''} onChange={e=>value('title',e.target.value)} /></label>
          <label className="label">Issue type<select className="field" disabled={!canEdit} value={draft.type || 'TASK'} onChange={e=>value('type',e.target.value)}>{['TASK','BUG','STORY','EPIC','MILESTONE'].map(t=><option key={t}>{t}</option>)}</select></label>
          <label className="label">Description<textarea className="field" rows={4} disabled={!canEdit} value={draft.description || ''} onChange={e=>value('description',e.target.value)} /></label>
          <div className="grid grid-cols-2 gap-3"><label className="label">Status<select className="field" disabled={!canEdit} value={draft.status_id || ''} onChange={e=>value('status_id',e.target.value)}>{statuses.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label className="label">Priority<select className="field" disabled={!canEdit} value={draft.priority || 'MEDIUM'} onChange={e=>value('priority',e.target.value as TaskPriority)}>{['URGENT','HIGH','MEDIUM','LOW'].map(p=><option key={p}>{p}</option>)}</select></label>
          <label className="label">Assignee<select className="field" disabled={!canEdit} value={draft.assignee_id || ''} onChange={e=>value('assignee_id',e.target.value)}><option value="">Unassigned</option>{members.filter(m=>m.status==='ACTIVE' && m.user).map(m=><option key={m.id} value={m.user!.id}>{m.user!.full_name}</option>)}</select></label>
          <label className="label">Sprint<select className="field" disabled={!canEdit} value={draft.sprint_id || ''} onChange={e=>value('sprint_id',e.target.value)}><option value="">Backlog</option>{project?.sprints?.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <label className="label">Story points<input type="number" min="0" step="0.5" className="field" disabled={!canEdit} value={draft.story_points ?? ''} onChange={e=>value('story_points',e.target.value?Number(e.target.value):null)}/></label><label className="label">Estimated hours<input type="number" min="0" step="0.5" className="field" disabled={!canEdit} value={draft.estimated_hours ?? ''} onChange={e=>value('estimated_hours',e.target.value?Number(e.target.value):null)}/></label>
          <label className="label">Start date<input type="date" className="field" disabled={!canEdit} value={draft.start_date || ''} onChange={e=>value('start_date',e.target.value)}/></label><label className="label">Due date<input type="date" className="field" disabled={!canEdit} value={draft.due_date || ''} onChange={e=>value('due_date',e.target.value)}/></label></div>
          <label className="label">Repeat on completion<select className="field" disabled={!canEdit} value={draft.recurrence?.frequency || ''} onChange={e=>value('recurrence',e.target.value?{frequency:e.target.value,interval:1}:null)}><option value="">Does not repeat</option><option value="DAILY">Daily</option><option value="WEEKLY">Weekly</option><option value="MONTHLY">Monthly</option><option value="CRON">Custom cron</option></select></label>
          {draft.recurrence && <div className="grid grid-cols-2 gap-3"><label className="label">Interval<input className="field" type="number" min={1} max={365} value={draft.recurrence.interval || 1} onChange={e=>value('recurrence',{...draft.recurrence,interval:Number(e.target.value)})}/></label><label className="label">Repeat until<input className="field" type="date" value={draft.recurrence.until || ''} onChange={e=>value('recurrence',{...draft.recurrence,until:e.target.value || null})}/></label>{draft.recurrence.frequency==='CRON' && <label className="label">Cron expression<input className="field" placeholder="0 9 * * 1-5" required value={draft.recurrence.cron || ''} onChange={e=>value('recurrence',{...draft.recurrence,cron:e.target.value})}/></label>}{draft.recurrence.frequency==='WEEKLY' && <label className="label">Weekdays (Monday = 0)<input className="field" placeholder="0,2,4" value={draft.recurrence.weekdays?.join(',') || ''} onChange={e=>value('recurrence',{...draft.recurrence,weekdays:e.target.value?e.target.value.split(',').map(Number):[]})}/></label>}</div>}
          {canEdit && <button className="btn-primary" disabled={busy}>Save changes</button>}
        </form>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Subtasks</h2>{task.subtasks?.map(sub=><label className="flex gap-3 items-center text-sm" key={sub.id}><input type="checkbox" checked={sub.is_completed} disabled={!canEdit || busy} onChange={e=>{const state=statuses.find(s=>s.category===(e.target.checked?'DONE':'TODO')); if(state) run(()=>api.updateTask(sub.id,{status_id:state.id}));}} /><span className={sub.is_completed?'line-through text-slate-500':''}>{sub.title}</span></label>)}{canEdit && <form className="flex gap-2" onSubmit={e=>submit(e,values=>api.addSubtask(task.id,String(values.get('title'))))}><input className="field" name="title" aria-label="Subtask title" required placeholder="Add a subtask…"/><button className="btn" disabled={busy}>Add</button></form>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Checklist</h2>{checklist.map(item=><label className="flex gap-3 items-center text-sm" key={item.id}><input type="checkbox" checked={item.is_completed} disabled={!canEdit || busy} onChange={e=>run(()=>api.updateChecklist(task.id,item.id,e.target.checked))}/>{item.title}</label>)}{canEdit && <form className="flex gap-2" onSubmit={e=>submit(e,v=>api.addChecklist(task.id,String(v.get('title'))))}><input className="field" name="title" aria-label="Checklist item" required placeholder="Add a checklist item…"/><button className="btn" disabled={busy}>Add</button></form>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Dependencies</h2>{task.dependencies_out?.map(dep=><div className="flex justify-between items-center gap-2 text-sm" key={dep.id}><span>{dep.dependency_type==='RELATES_TO'?'Related to':'Blocks'} {candidates.find(t=>t.id===dep.successor_id)?.short_id || 'Linked issue'}</span>{canEdit && <button className="btn" disabled={busy} onClick={()=>run(()=>api.removeDependency(task.id,dep.id))}>Remove</button>}</div>)}{canEdit && <form className="flex gap-2" onSubmit={e=>submit(e,v=>api.addDependency(task.id,String(v.get('successor'))))}><select name="successor" className="field" required aria-label="Issue this blocks"><option value="">Choose an issue…</option>{candidates.map(t=><option key={t.id} value={t.id}>{t.short_id} · {t.title}</option>)}</select><button className="btn" disabled={busy}>Link</button></form>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Attachments</h2>{task.attachments?.map(file=><a key={file.id} className="flex gap-2 items-center text-sm text-sky-400 hover:underline" href={downloadUrls[file.id]} target="_blank" rel="noreferrer"><Paperclip size={14}/>{file.file_name} · {Math.ceil(file.file_size/1024)} KB</a>)}{canEdit && <label className="label">Upload a file (up to 25 MB)<input aria-label="Upload attachment" className="field" type="file" disabled={busy} onChange={e=>{const file=e.target.files?.[0];if(file) run(()=>api.uploadAttachment(task.id,file));e.target.value='';}}/></label>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">GitHub</h2>{['github_issue','github_pr','github_workflow_run','github_pull_request_review'].map(key=>{const link=task.custom_fields?.[key];return link && <p className="text-sm" key={key}>{link.url && /^https:\/\/github\.com\//.test(link.url) ? <a className="text-sky-400 underline" href={link.url} target="_blank" rel="noreferrer">{link.title || key.replace('github_','').replace(/_/g,' ')} {link.number ? `#${link.number}`:''}</a> : <span>{key}</span>} · {link.conclusion || link.state || link.status || 'Linked'}</p>;})}{canDelete && <button className="btn" disabled={busy} onClick={()=>run(()=>api.publishGithubIssue(task.id))}>Publish issue to connected repository</button>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Designs</h2>{figma.map(link=><a className="block rounded-lg border border-slate-800 p-3 text-sky-400 text-sm" key={link.id} href={link.figma_url} target="_blank" rel="noreferrer">{link.thumbnail_url && <img className="rounded mb-2 max-h-40" src={link.thumbnail_url} alt={link.file_name || 'Figma design'} loading="lazy"/>}<span className="flex gap-2 items-center">{link.file_name || 'Open in Figma'} <ExternalLink size={14}/></span></a>)}{canEdit && <form className="flex gap-2" onSubmit={e=>submit(e,v=>api.attachFigma(task.id,String(v.get('url'))))}><input type="url" name="url" className="field" required aria-label="Figma URL" placeholder="Paste a Figma design link…"/><button className="btn" disabled={busy}>Attach</button></form>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Custom fields</h2>{Object.entries(task.custom_fields || {}).map(([key,val])=><p className="text-sm" key={key}><span className="text-slate-500 mr-2">{key}</span>{String(val)}</p>)}{canEdit && <form className="flex gap-2" onSubmit={e=>submit(e,v=>api.updateTask(task.id,{custom_fields:{[String(v.get('name'))]:String(v.get('value'))}}))}><input className="field" name="name" required aria-label="Custom field name" placeholder="Field name"/><input className="field" name="value" aria-label="Custom field value" placeholder="Value"/><button className="btn" disabled={busy}>Save</button></form>}</section>
        <section className="space-y-3"><h2 className="font-semibold text-sm">Discussion</h2>{task.comments?.map(comment=><article className="rounded-lg border border-slate-800 p-3 space-y-2" key={comment.id}><div className="text-xs text-slate-500">{comment.author?.full_name || 'Team member'} · {new Date(comment.created_at).toLocaleString()}</div><p className="whitespace-pre-wrap text-sm">{comment.content}</p></article>)}{canEdit && <form className="space-y-2" onSubmit={e=>submit(e,v=>api.addComment(task.id,String(v.get('content'))))}><textarea rows={3} name="content" aria-label="Comment" required className="field" placeholder="Write an update…"/><button className="btn" disabled={busy}>Post comment</button></form>}</section>
        {canDelete && <div className="border-t border-slate-800 pt-4">{confirmDelete?<div className="flex items-center gap-3"><span className="text-sm text-red-300">Delete this issue and its subtasks?</span><button className="btn" disabled={busy} onClick={()=>run(async()=>{await api.deleteTask(task.id);onClose();})}>Delete permanently</button><button className="btn" onClick={()=>setConfirmDelete(false)}>Cancel</button></div>:<button className="btn text-red-400" onClick={()=>setConfirmDelete(true)}><Trash2 size={14}/>Delete issue</button>}</div>}
      </div>
    </section>
  </div>;
}
