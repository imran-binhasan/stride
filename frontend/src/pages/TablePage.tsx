import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Project, TableResult, Task, TaskPriority } from '../types';

export function TablePage({ project, onSelectTask, revision, canEdit }: {project: Project; onSelectTask: (task: Task) => void; revision: number; canEdit: boolean}) {
  const [result, setResult] = useState<TableResult | null>(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('position');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [localRevision, setLocalRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setError(''); setResult(null);
    const timer = setTimeout(() => api.getTable(project.id, {search, sort_by: sort, status_id: status, offset: String(offset), limit: '25'})
      .then(data => { if (!cancelled) setResult(data); })
      .catch(e => { if (!cancelled) setError(e.message); }), 200);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [project.id, search, sort, status, offset, revision, localRevision]);
  useEffect(() => setOffset(0), [project.id, search, status]);
  async function update(id: string, values: Partial<Task>) {
    try { await api.updateTask(id, values); setLocalRevision(v => v + 1); }
    catch (e) { setError((e as Error).message); }
  }
  return <section className="flex-1 overflow-auto p-4 md:p-6 space-y-5">
    <div><h1 className="text-xl font-bold">Issues</h1><p className="text-sm text-slate-400">Sort, filter, and update your team’s work.</p></div>
    <div className="flex flex-wrap gap-3">
      <input aria-label="Search issues" className="field max-w-xs" placeholder="Search issues…" value={search} onChange={e => setSearch(e.target.value)} />
      <select aria-label="Filter by status" className="field w-auto" value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option>{project.statuses.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <select aria-label="Sort issues" className="field w-auto" value={sort} onChange={e => setSort(e.target.value)}><option value="position">Board order</option><option value="title">Title</option><option value="due_date">Due date</option><option value="created_at">Created</option></select>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    {!result && !error && <p className="text-slate-400">Loading issues…</p>}
    {result && <><div className="overflow-x-auto rounded-xl border border-slate-800"><table className="w-full text-left text-sm"><thead className="bg-slate-900 text-slate-400"><tr>{['Issue', 'Status', 'Priority', 'Due date', 'Assignee'].map(h => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-800">{result.items.map(task => <tr key={task.id} className="hover:bg-slate-900/60">
      <td className="p-3 min-w-64"><button onClick={() => onSelectTask(task)} className="text-left hover:text-sky-300"><span className="mr-3 font-mono text-xs text-sky-400">{task.short_id}</span>{task.title}</button></td>
      <td className="p-3"><select aria-label={`Status for ${task.short_id}`} disabled={!canEdit} className="field min-w-32" value={task.status_id} onChange={e => update(task.id, {status_id: e.target.value})}>{project.statuses.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></td>
      <td className="p-3"><select aria-label={`Priority for ${task.short_id}`} disabled={!canEdit} className="field" value={task.priority} onChange={e => update(task.id, {priority: e.target.value as TaskPriority})}>{['URGENT','HIGH','MEDIUM','LOW'].map(p => <option key={p}>{p}</option>)}</select></td>
      <td className="p-3"><input aria-label={`Due date for ${task.short_id}`} disabled={!canEdit} className="field" type="date" value={task.due_date || ''} onChange={e => update(task.id, {due_date: e.target.value || null})} /></td>
      <td className="p-3 text-slate-400">{task.assignee?.full_name || 'Unassigned'}</td>
    </tr>)}</tbody></table>{!result.items.length && <p className="p-10 text-center text-slate-400">No issues match these filters.</p>}</div>
    <div className="flex items-center justify-between text-sm text-slate-400"><span>{result.total} issues</span><div className="flex gap-2"><button className="btn" disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 25))}>Previous</button><button className="btn" disabled={offset + 25 >= result.total} onClick={() => setOffset(v => v + 25)}>Next</button></div></div></>}
  </section>;
}
