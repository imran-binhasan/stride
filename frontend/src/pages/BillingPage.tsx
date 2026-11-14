import {useEffect,useState} from 'react';
import {api} from '../services/api';
interface Billing {tier:string;max_members:number;max_projects:number;subscription:{status:string}|null;plans:{tier:string;max_members:number;max_projects:number}[];invoices:{id:string;amount:number;currency:string;status:string;created_at:string}[];}
export function BillingPage({canManage}:{canManage:boolean}){
 const [data,setData]=useState<Billing|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{if(canManage)api.billingStatus<Billing>().then(setData).catch(e=>setError(e.message));},[canManage]);
 async function action(name:'checkout'|'portal',tier?:string){setBusy(true);setError('');try{const {url}=await api.billingAction(name,tier);const target=new URL(url);if(target.protocol!=='https:'||!['checkout.stripe.com','billing.stripe.com'].includes(target.hostname))throw new Error('Unexpected billing destination');window.location.assign(url);}catch(e){setError((e as Error).message);setBusy(false);}}
 if(!canManage)return <p className="p-6">Billing is available to organization owners and administrators.</p>;
 return <section className="p-6 overflow-auto space-y-6"><h1 className="text-xl font-semibold">Organization billing</h1>{error&&<p role="alert" className="error">{error}</p>}{data&&<>
 <div className="panel space-y-2"><h2>{data.tier} plan · {data.subscription?.status || 'Free account'}</h2><p className="text-slate-400">{data.max_members} members · {data.max_projects} projects</p>{data.subscription&&<button className="btn" disabled={busy} onClick={()=>action('portal')}>Manage subscription and invoices</button>}</div>
 <div className="flex flex-wrap gap-4">{data.plans.map(plan=><article className="panel space-y-3" key={plan.tier}><h2>{plan.tier}</h2><p>{plan.max_members} members · {plan.max_projects} projects</p><button className="btn-primary" disabled={busy||['ACTIVE','TRIALING','PAST_DUE'].includes(data.subscription?.status || '')} onClick={()=>action('checkout',plan.tier)}>Review pricing and subscribe</button></article>)}</div>
 {!data.plans.length&&<p className="text-slate-400">Paid plans are unavailable until billing is configured by your operator.</p>}
 <p className="text-sm text-slate-400">Pricing, payment details, plan changes, and cancellation are handled on the billing provider’s secure page. Subscription access updates after verified provider confirmation.</p>
 <h2 className="font-semibold">Invoice history</h2>{data.invoices.map(i=><div key={i.id} className="panel flex flex-wrap justify-between gap-3"><span>{new Date(i.created_at).toLocaleDateString()}</span><span>{i.amount.toFixed(2)} {i.currency}</span><span>{i.status}</span></div>)}{!data.invoices.length&&<p>No invoices yet.</p>}
 </>}</section>;
}
