import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {beforeEach,expect,it,vi} from 'vitest';
import {invoke} from '@tauri-apps/api/core';
import {App} from './App';
vi.mock('@tauri-apps/api/core',()=>({invoke:vi.fn(),isTauri:()=>true}));
const blank={connected:false,entry:null,activity_score:null,screenshots:0,input_available:false,paused_for_idle:false,error:null};
beforeEach(()=>{vi.mocked(invoke).mockReset();localStorage.clear();});
it('keeps failed logins on the login screen without creating an offline token',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>{if(command==='get_daemon_status')return blank as never;throw new Error('Invalid credentials');});
 render(<App/>);
 fireEvent.change(screen.getByLabelText('Email'),{target:{value:'employee@example.com'}});
 fireEvent.change(screen.getByLabelText('Password'),{target:{value:'wrong-password'}});
 fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
 expect(screen.getByLabelText('Password')).toBeInTheDocument();
 expect(localStorage.getItem('stride_desktop_token')).toBeNull();
});
it('uses server tasks and leaves tracking stopped when start fails',async()=>{
 vi.mocked(invoke).mockImplementation(async(command,args)=>{
  if(command==='get_daemon_status'||command==='select_organization')return {...blank,connected:true} as never;
  if(command==='read_api'){
   const path=(args as {path:string}).path;
   if(path==='/organizations')return [{id:'org',name:'Team'}] as never;
   if(path.includes('/workspaces'))return [{id:'ws',name:'Workspace'}] as never;
   if(path.includes('/projects/'))return [{id:'project',name:'Project'}] as never;
   return [{id:'task',short_id:'P-1',title:'Real task'}] as never;
  }
  if(command==='start_tracking')throw new Error('Server unavailable');
  return undefined as never;
 });
 render(<App/>);
 fireEvent.change(await screen.findByLabelText('Organization'),{target:{value:'org'}});
 await screen.findByRole('option',{name:'Project'});
 fireEvent.change(screen.getByLabelText('Project'),{target:{value:'project'}});
 await screen.findByRole('option',{name:'P-1: Real task'});
 await waitFor(()=>expect(screen.getByRole('button',{name:'Start timer'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'Start timer'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Server unavailable');
 expect(screen.getByText('Ready to track')).toBeInTheDocument();
 expect(screen.getByLabelText('Session duration')).toHaveTextContent('00:00:00');
});
