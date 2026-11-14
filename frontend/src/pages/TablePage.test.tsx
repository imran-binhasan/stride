import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../services/api';
import { TablePage } from './TablePage';
import { Project, Task } from '../types';

afterEach(() => vi.restoreAllMocks());
const project = {id:'p1', name:'Project', statuses:[{id:'todo',name:'To do'},{id:'done',name:'Done'}]} as Project;
const task = {id:'t1',short_id:'P-1',title:'Ship workflow',status_id:'todo',priority:'HIGH',due_date:'2026-10-25'} as Task;

it('filters issues through the table API and opens task details', async () => {
  const list = vi.spyOn(api,'getTable').mockResolvedValue({items:[task],total:1,offset:0,limit:25});
  const select = vi.fn();
  render(<TablePage project={project} onSelectTask={select} revision={0} canEdit />);
  fireEvent.click(await screen.findByRole('button',{name:/Ship workflow/}));
  expect(select).toHaveBeenCalledWith(task);
  fireEvent.change(screen.getByRole('textbox',{name:'Search issues'}),{target:{value:'workflow'}});
  await waitFor(()=>expect(list).toHaveBeenLastCalledWith('p1',expect.objectContaining({search:'workflow'})));
});

it('clears a due date through an explicit null update', async () => {
  vi.spyOn(api,'getTable').mockResolvedValue({items:[task],total:1,offset:0,limit:25});
  const update = vi.spyOn(api,'updateTask').mockResolvedValue(task);
  render(<TablePage project={project} onSelectTask={()=>{}} revision={0} canEdit />);
  const date = await screen.findByLabelText('Due date for P-1');
  fireEvent.change(date,{target:{value:''}});
  await waitFor(()=>expect(update).toHaveBeenCalledWith('t1',{due_date:null}));
});
