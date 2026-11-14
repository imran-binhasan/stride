import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from './services/api';
import { App } from './App';
import { Project, Task } from './types';

vi.mock('./hooks/useRealtime', () => ({useRealtime: () => ({broadcast: vi.fn(), connected:true})}));
vi.mock('./pages/KanbanPage', () => ({KanbanPage: ({onSelectTask}: {onSelectTask: (task: Task) => void}) => <button onClick={()=>onSelectTask({id:'task-1'} as Task)}>Open issue</button>}));
vi.mock('./components/TaskDrawer', () => ({TaskDrawer: ({onClose,onUpdate}: {onClose: ()=>void;onUpdate: ()=>void}) => <div role="dialog"><button onClick={onUpdate}>Refresh issue</button><button onClick={onClose}>Close issue</button></div>}));
afterEach(()=>{vi.restoreAllMocks();api.clearAuth();});

it('keeps a closed drawer closed when an earlier refresh returns', async () => {
  api.setAuth('token', 'refresh', 'org-1');
  const project = {id:'project-1',name:'Project',key:'PRJ',statuses:[]} as Project;
  vi.spyOn(api,'getMe').mockResolvedValue({id:'user-1',full_name:'Owner'} as never);
  vi.spyOn(api,'listMyOrganizations').mockResolvedValue([{id:'org-1',name:'Org',role:'ORG_OWNER'}] as never);
  vi.spyOn(api,'listWorkspaces').mockResolvedValue([{id:'workspace-1'}] as never);
  vi.spyOn(api,'listWorkspaceProjects').mockResolvedValue([project]);
  vi.spyOn(api,'getProject').mockResolvedValue(project);
  vi.spyOn(api,'listMembers').mockResolvedValue([]);
  vi.spyOn(api,'getActiveTimer').mockResolvedValue(null);
  vi.spyOn(api,'getKanban').mockResolvedValue({project_id:project.id,total_tasks:1,columns:[]});
  const task = {id:'task-1',title:'Issue'} as Task;
  let resolveRefresh: (task: Task) => void = () => {};
  vi.spyOn(api,'getTask').mockResolvedValueOnce(task).mockImplementationOnce(()=>new Promise(resolve=>{resolveRefresh=resolve;}));
  render(<App/>);
  fireEvent.click(await screen.findByRole('button',{name:'Open issue'}));
  fireEvent.click(await screen.findByRole('button',{name:'Refresh issue'}));
  fireEvent.click(screen.getByRole('button',{name:'Close issue'}));
  resolveRefresh(task);
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});
