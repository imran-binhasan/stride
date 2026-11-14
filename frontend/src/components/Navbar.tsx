import { useEffect, useState } from 'react';
import { LogOut, Radio, Sparkles, Square, Zap } from 'lucide-react';
import { ActiveTimer, MyOrg, Project, UserProfile } from '../types';
import { api } from '../services/api';

interface Props {
  organizations: MyOrg[]; activeOrgId: string | null; onSelectOrganization: (id: string) => void;
  connected: boolean; currentProject: Project | null; projects: Project[]; onSelectProject: (project: Project) => void;
  activeTimer: ActiveTimer | null; onRefreshTimer: () => void; onOpenAIDrawer: () => void;
  user: UserProfile | null; onLogout: () => void; canUseAI?: boolean;
}
export function Navbar({organizations, activeOrgId, onSelectOrganization, connected, currentProject, projects, onSelectProject, activeTimer, onRefreshTimer, onOpenAIDrawer, user, onLogout, canUseAI = true}: Props) {
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(0); const [stopping, setStopping] = useState(false);
  useEffect(()=>{if(!activeTimer){setSeconds(0);return;} const update=()=>setSeconds(Math.max(0,Math.floor((Date.now()-new Date(activeTimer.start_time).getTime())/1000)));update();const timer=setInterval(update,1000);return()=>clearInterval(timer);},[activeTimer]);
  const duration = `${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
  return <header className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-900/90 px-4 py-3 shrink-0">
    <div className="flex items-center gap-2"><span className="w-8 h-8 rounded-lg bg-sky-500 grid place-items-center"><Zap size={18} fill="white"/></span><span className="text-sm font-bold tracking-tight">STRIDE</span></div>
    <div className="order-3 md:order-none flex w-full md:w-auto md:flex-1 gap-2 min-w-0">
      <select aria-label="Organization" className="field flex-1 min-w-0 md:max-w-40 text-xs" value={activeOrgId || ''} onChange={e=>onSelectOrganization(e.target.value)}>{organizations.map(org=><option key={org.id} value={org.id}>{org.name}</option>)}</select>
      <select aria-label="Project" className="field flex-1 min-w-0 md:max-w-64 text-xs" value={currentProject?.id || ''} onChange={e=>{const project=projects.find(p=>p.id===e.target.value);if(project)onSelectProject(project);}}>{projects.map(p=><option key={p.id} value={p.id}>{p.key} · {p.name}</option>)}{!projects.length && <option value="">No projects yet</option>}</select>
    </div>
    <div className="ml-auto flex items-center gap-3">
      {activeTimer && <div className="flex items-center gap-2 rounded-lg border border-emerald-800 bg-emerald-950/40 px-2 py-1 text-emerald-400 text-xs font-mono"><span>{duration}</span><button aria-label="Stop active timer" disabled={stopping} onClick={async()=>{setStopping(true);try{await api.stopTimer();onRefreshTimer();setError('');}catch(e){setError((e as Error).message);}finally{setStopping(false);}}}><Square size={13}/></button></div>}
      {canUseAI && <button onClick={onOpenAIDrawer} className="btn hidden lg:inline-flex text-xs"><Sparkles size={14}/>AI planning</button>}
      <div className="hidden lg:flex gap-1.5 items-center text-xs text-slate-400" role="status"><Radio size={13} className={connected?'text-emerald-400':'text-slate-500'}/>{connected?'Live sync':'Connecting…'}</div>
      <span title={`${user?.full_name || ''} · ${user?.email || ''}`} className="w-7 h-7 rounded-full bg-slate-700 grid place-items-center text-xs text-sky-300">{user?.full_name?.charAt(0) || 'U'}</span>
      <button className="text-slate-400 hover:text-red-300" aria-label="Log out" onClick={onLogout}><LogOut size={17}/></button>
    </div>
    {error && <p role="alert" className="error w-full">{error}</p>}
  </header>;
}
