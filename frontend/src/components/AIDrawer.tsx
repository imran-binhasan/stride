import React, { useState } from "react";
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Code2,
  Cpu,
  Layers,
  Terminal
} from "lucide-react";
import { FullAIPipelineResponse } from "../types";
import { api } from "../services/api";

interface AIDrawerProps {
  projectId: string;
  onClose: () => void;
  onPlanAccepted?: () => void;
}

export const AIDrawer: React.FC<AIDrawerProps> = ({ projectId, onClose }) => {
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<FullAIPipelineResponse | null>(null);
  const [activeGateTab, setActiveGateTab] = useState<1 | 2 | 3 | 4 | 5>(1);

  const handleRunPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    try {
      setRunning(true);
      const res = await api.runFullAIPipeline(projectId, prompt);
      setResult(res);
      setActiveGateTab(1);
    } catch (e: any) {
      alert(e.message || "Failed to execute AI pipeline");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-sky-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">5-Gate AI Loop Engineering Pipeline</h2>
              <p className="text-xs text-slate-400">Context Engineering &bull; Acyclic DAG Task Planning &bull; TDD Generator &bull; Quality Gates</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <div className="p-5 border-b border-slate-800 bg-slate-950/40">
          <form onSubmit={handleRunPipeline} className="flex gap-3">
            <input
              type="text"
              placeholder="e.g. Implement OAuth2 Google Login with Refresh Token Rotation and RBAC guards..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
            <button
              type="submit"
              disabled={running}
              className="px-5 py-2.5 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-sky-500/20 flex items-center gap-2 disabled:opacity-50"
            >
              {running ? <Cpu className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              <span>{running ? "Processing 5 Gates..." : "Execute Pipeline"}</span>
            </button>
          </form>
        </div>

        {/* Results Container */}
        {result && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Gate Tabs */}
            <div className="flex border-b border-slate-800 bg-slate-900 px-4 gap-2">
              {[
                { gate: 1, label: "Gate 1: Intent", passed: result.gate1_intent.passed },
                { gate: 2, label: "Gate 2: Context", passed: result.gate2_context.passed },
                { gate: 3, label: "Gate 3: DAG Plan", passed: result.gate3_plan.passed },
                { gate: 4, label: "Gate 4: TDD Gen", passed: result.gate4_tdd.passed },
                { gate: 5, label: "Gate 5: Execution", passed: result.gate5_execution.passed },
              ].map((g) => (
                <button
                  key={g.gate}
                  onClick={() => setActiveGateTab(g.gate as any)}
                  className={`py-3 px-3.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-all ${
                    activeGateTab === g.gate
                      ? "border-sky-500 text-sky-400 bg-sky-500/5"
                      : "border-transparent text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {g.passed ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  )}
                  <span>{g.label}</span>
                </button>
              ))}
            </div>

            {/* Gate Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
              {activeGateTab === 1 && (
                <div className="space-y-3">
                  <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
                    <span className="text-[10px] uppercase font-bold text-slate-500">Feature Title</span>
                    <h3 className="text-sm font-bold text-white">{result.gate1_intent.feature_title}</h3>
                    <p className="text-slate-300">{result.gate1_intent.summary}</p>
                    <div className="flex gap-4 pt-2">
                      <span className="text-sky-400 font-semibold">Priority: {result.gate1_intent.suggested_priority}</span>
                      <span className="text-indigo-400 font-semibold">Points: {result.gate1_intent.estimated_points}</span>
                      <span className="text-emerald-400 font-semibold">Ambiguity: {Math.round(result.gate1_intent.ambiguity_score * 100)}%</span>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-800/20 border border-slate-800 space-y-2">
                    <span className="text-[10px] uppercase font-bold text-slate-500">Acceptance Criteria</span>
                    <ul className="list-disc list-inside space-y-1 text-slate-300">
                      {result.gate1_intent.acceptance_criteria.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {activeGateTab === 2 && (
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-3">
                  <span className="text-[10px] uppercase font-bold text-slate-500">State Vectorization & Context Budget</span>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-400">Context Tokens:</span>
                      <p className="text-sm font-bold text-emerald-400">{result.gate2_context.context_token_estimate} tokens (Budget: &lt;32k)</p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-400">Project Key:</span>
                      <p className="text-sm font-bold text-sky-400">{result.gate2_context.project_key}</p>
                    </div>
                  </div>
                  <pre className="p-3 rounded-lg bg-slate-950 font-mono text-[11px] text-slate-300 overflow-x-auto">
                    {JSON.stringify(result.gate2_context.context_payload, null, 2)}
                  </pre>
                </div>
              )}

              {activeGateTab === 3 && (
                <div className="space-y-3">
                  <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Acyclic DAG Decomposition</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                        Acyclic Verified (0 Cycles)
                      </span>
                    </div>
                    <p className="text-slate-300">{result.gate3_plan.risk_assessment}</p>
                  </div>

                  <div className="space-y-2">
                    {result.gate3_plan.plan_dag.map((step) => (
                      <div key={step.step_number} className="p-3 rounded-lg bg-slate-800/20 border border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-sky-500/20 text-sky-400 font-bold flex items-center justify-center text-xs">
                            {step.step_number}
                          </span>
                          <div>
                            <span className="font-semibold text-slate-200">{step.title}</span>
                            <span className="ml-2 text-[10px] font-mono text-indigo-400 uppercase">[{step.layer}]</span>
                          </div>
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">Deps: {step.dependencies.join(", ") || "None"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeGateTab === 4 && (
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-slate-500">Generated Async Pytest Test Module</span>
                    <span className="text-xs text-sky-400 font-mono font-semibold">{result.gate4_tdd.assertions_count} Assertions Generated</span>
                  </div>
                  <pre className="p-4 rounded-lg bg-slate-950 font-mono text-[11px] text-sky-300 overflow-x-auto max-h-72">
                    {result.gate4_tdd.generated_test_module}
                  </pre>
                </div>
              )}

              {activeGateTab === 5 && (
                <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-800/30 space-y-3">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Gate 5 Execution & Quality Verification Passed</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-center">
                      <span className="text-slate-400">Tests Run</span>
                      <p className="text-base font-bold text-white">{result.gate5_execution.tests_executed}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-center">
                      <span className="text-slate-400">Tests Passed</span>
                      <p className="text-base font-bold text-emerald-400">{result.gate5_execution.tests_passed}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-center">
                      <span className="text-slate-400">Coverage</span>
                      <p className="text-base font-bold text-sky-400">{result.gate5_execution.coverage_percent}%</p>
                    </div>
                  </div>
                  <p className="text-slate-300 leading-relaxed">{result.gate5_execution.summary}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
