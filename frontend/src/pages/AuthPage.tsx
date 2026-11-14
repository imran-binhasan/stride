import React, { useState, useEffect } from "react";
import { Zap, Lock, Mail, User, Building, ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "../services/api";

interface AuthPageProps {
  onSuccess: () => void;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onSuccess }) => {
  const [providers, setProviders] = useState<string[]>([]);
  useEffect(() => {
    api.oauthProviders().then(setProviders).catch(() => {});
    const ticket = new URLSearchParams(window.location.hash.slice(1)).get('oauth_ticket');
    if (ticket) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
      setLoading(true);
      api.oauthExchange(ticket).then(tokens => {api.setAuth(tokens.access_token,tokens.refresh_token);onSuccess();})
        .catch(e => setError(e.message)).finally(() => setLoading(false));
    }
  }, []);
  const [isInvite, setIsInvite] = useState(false);
  const [inviteToken, setInviteToken] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isInvite) {
        const res = await api.acceptInvite(inviteToken, fullName, password);
        api.setAuth(res.access_token, res.refresh_token);
      } else if (isRegister) {
        const res = await api.register({
          email,
          password,
          full_name: fullName,
          organization_name: orgName,
        });
        api.setAuth(res.data.tokens.access_token, res.data.tokens.refresh_token);
      } else {
        const res = await api.login({ email, password });
        api.setAuth(res.access_token, res.refresh_token);
      }
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 selection:bg-sky-500 selection:text-white">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Brand */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 items-center justify-center shadow-lg shadow-sky-500/20 mb-2">
            <Zap className="w-6 h-6 text-white fill-white" />
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">
            STRIDE
          </h1>
          <p className="text-xs text-slate-400">
            Project Management &bull; Workforce Intelligence &bull; AI Engineering
          </p>
        </div>

        {providers.length > 0 && <div className="flex gap-3">{providers.map(p => <a key={p} className="btn flex-1 text-center capitalize" href={api.oauthStart(p)}>Continue with {p}</a>)}</div>}
        {/* Tab Toggle */}
        <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            type="button"
            onClick={() => {setIsRegister(false);setIsInvite(false);}}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
              !isRegister ? "bg-slate-800 text-white shadow-sm" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {setIsRegister(true);setIsInvite(false);}}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
              isRegister ? "bg-slate-800 text-white shadow-sm" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Create Organization
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
            {error}
          </div>
        )}

        <button className="text-xs text-sky-400" type="button" onClick={() => {setIsInvite(v => !v);setIsRegister(false);}}>Have an invitation? {isInvite ? "Return to sign in" : "Join your team"}</button>
        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {isInvite && <div className="space-y-3"><label className="label">Invitation token<input className="field" required value={inviteToken} onChange={e=>setInviteToken(e.target.value)}/></label><label className="label">Full name<input className="field" required minLength={2} value={fullName} onChange={e=>setFullName(e.target.value)}/></label><p className="text-xs text-slate-400">Use your existing account password if you already have an account.</p></div>}
          {isRegister && (
            <>
              <div>
                <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                    placeholder="Jane Doe"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Company / Organization</label>
                <div className="relative">
                  <Building className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                    placeholder="Acme Labs Inc."
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Work Email</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="email"
                required={!isInvite}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                placeholder="name@company.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-sky-500/20 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] disabled:opacity-50"
          >
            <span>{loading ? "Authenticating..." : isInvite ? "Accept invitation" : isRegister ? "Create Account & Workspace" : "Sign In to Workspace"}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="pt-2 text-center text-[11px] text-slate-500 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Argon2 Secure Authentication &bull; Multi-Tenant SaaS</span>
        </div>
      </div>
    </div>
  );
};
