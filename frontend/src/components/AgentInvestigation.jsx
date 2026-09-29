import React, { useState } from 'react';

export default function AgentInvestigation({ 
  incident, 
  investigation, 
  loading, 
  onAccept, 
  onReject, 
  onEdit, 
  onMarkObsolete,
  onApprovePolicy,
  isPolicyApproved
}) {
  const [showLogs, setShowLogs] = useState(false);

  if (loading) {
    return (
      <div className="bg-[#0F1626] border border-gray-800 rounded-xl p-8 flex flex-col items-center justify-center h-full text-center">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <div className="text-base font-bold text-gray-200">Querying Hindsight Memory Bank...</div>
        <div className="text-xs text-gray-400 mt-1 max-w-sm">
          Extracting error signatures, comparing live telemetry deltas, and verifying team policies.
        </div>
      </div>
    );
  }

  if (!incident || !investigation) {
    return (
      <div className="bg-[#0F1626] border border-gray-800 rounded-xl p-8 flex flex-col items-center justify-center h-full text-center text-gray-400">
        <svg className="w-12 h-12 mb-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <div className="text-sm font-semibold text-gray-300">No Incident Selected</div>
        <div className="text-xs text-gray-400 mt-1">Select an incident from the feed or click "Run Next Incident" to triage.</div>
      </div>
    );
  }

  const rec = investigation.recommendation;
  const isHighConf = rec.confidence === 'HIGH';
  const isMedConf = rec.confidence === 'MEDIUM';
  const isApprovalNeeded = rec.approval_required && !isPolicyApproved;

  return (
    <div className="bg-[#0F1626] border border-gray-800 rounded-xl flex flex-col h-full overflow-hidden shadow-xl">
      {/* Investigation Header */}
      <div className="p-4 border-b border-gray-800 bg-[#131C31] flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-mono text-sm font-bold text-blue-400">{incident.id}</span>
            <span className="text-xs text-gray-400 font-mono">[{incident.service}]</span>
            <span className="text-[10px] px-1.5 py-0.2 bg-blue-900/50 text-blue-300 border border-blue-700/50 rounded font-mono">
              Interaction #{investigation.interaction_number}
            </span>
          </div>
          <h2 className="text-sm font-semibold text-gray-200 mt-0.5">{incident.alert_text}</h2>
        </div>

        <div className="flex items-center space-x-3">
          <div className="text-right">
            <div className="text-[10px] text-gray-400 uppercase font-semibold">Triage Latency</div>
            <div className="text-xs font-mono font-bold text-emerald-400">{investigation.execution_time_ms} ms</div>
          </div>
          <div className={`px-2.5 py-1 rounded-md text-xs font-bold font-mono border ${
            isHighConf 
              ? 'bg-emerald-950/80 text-emerald-400 border-emerald-600/60'
              : isMedConf
              ? 'bg-amber-950/80 text-amber-400 border-amber-600/60'
              : 'bg-gray-800 text-gray-300 border-gray-700'
          }`}>
            {rec.confidence} CONFIDENCE
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Live Telemetry Snapshot */}
        <div className="grid grid-cols-4 gap-2 text-xs font-mono">
          <div className="bg-[#0A0F1A] p-2 rounded-lg border border-gray-800/80">
            <div className="text-gray-400 text-[10px]">MEMORY RSS / LIMIT</div>
            <div className="font-bold text-gray-200">
              {Math.round(incident.metrics.memory_rss_bytes / (1024*1024))}MB / {Math.round(incident.metrics.memory_limit_bytes / (1024*1024))}MB
            </div>
          </div>
          <div className="bg-[#0A0F1A] p-2 rounded-lg border border-gray-800/80">
            <div className="text-gray-400 text-[10px]">CPU USAGE</div>
            <div className="font-bold text-gray-200">{incident.metrics.cpu_percent}%</div>
          </div>
          <div className="bg-[#0A0F1A] p-2 rounded-lg border border-gray-800/80">
            <div className="text-gray-400 text-[10px]">KAFKA LAG</div>
            <div className={`font-bold ${incident.metrics.kafka_lag > 20000 ? 'text-amber-400 font-extrabold' : 'text-gray-200'}`}>
              {incident.metrics.kafka_lag.toLocaleString()} msgs
            </div>
          </div>
          <div className="bg-[#0A0F1A] p-2 rounded-lg border border-gray-800/80">
            <div className="text-gray-400 text-[10px]">P99 LATENCY</div>
            <div className="font-bold text-gray-200">{incident.metrics.p99_latency_ms}ms</div>
          </div>
        </div>

        {/* Recent Deploy Event Banner (if any) */}
        {incident.deploy_events && incident.deploy_events.length > 0 ? (
          <div className="bg-blue-950/30 border border-blue-800/50 rounded-lg p-2.5 flex items-start space-x-2 text-xs">
            <span className="text-blue-400 mt-0.5 font-mono">🚀</span>
            <div className="flex-1">
              <span className="font-bold text-blue-300">Recent Deploy Event: </span>
              <span className="font-mono text-gray-300">Commit {incident.deploy_events[0].commit_hash} by {incident.deploy_events[0].author}: "{incident.deploy_events[0].message}"</span>
              {incident.deploy_events[0].config_changes && (
                <span className="block text-[11px] font-mono text-amber-300 mt-0.5">
                  Config Changes: {JSON.stringify(incident.deploy_events[0].config_changes)}
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-gray-900/40 border border-gray-800/80 rounded-lg p-2 text-xs text-gray-400 font-mono">
            Steady-state operation. No recent deployments detected in the preceding 6 hours.
          </div>
        )}

        {/* Live Logs Collapsible */}
        <div className="border border-gray-800 rounded-lg overflow-hidden bg-[#0A0F1A]">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="w-full px-3 py-1.5 text-left text-xs font-mono font-semibold text-gray-400 hover:text-gray-200 flex justify-between items-center bg-[#0D1424]"
          >
            <span>▶ Live Logs Excerpt ({incident.logs ? incident.logs.length : 0} lines)</span>
            <span>{showLogs ? '▲ Hide' : '▼ Expand'}</span>
          </button>
          {showLogs && (
            <div className="p-3 text-[11px] font-mono text-gray-300 space-y-1 bg-black/40 overflow-x-auto">
              {incident.logs.map((log, idx) => (
                <div key={idx} className={log.includes('OutOfMemoryError') || log.includes('137') ? 'text-red-400 font-bold' : ''}>
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Golden Rule Guardrail Banner */}
        <div className="bg-amber-950/20 border border-amber-600/40 rounded-lg p-2.5 flex items-center space-x-2 text-[11px] text-amber-300">
          <span>⚖️</span>
          <span>
            <strong className="font-semibold">Guardrail Active:</strong> Live telemetry diffing strictly separates symptom correlation from root causality. Past fixes are never blindly applied without evidence alignment.
          </span>
        </div>

        {/* Agent Hypothesis Card */}
        <div className="bg-[#12192B] border border-gray-800 rounded-lg p-4">
          <div className="text-[10px] uppercase font-bold text-blue-400 tracking-wider mb-1">Synthesized Hypothesis</div>
          <div className="text-sm font-bold text-gray-100 leading-snug">
            {investigation.hypothesis}
          </div>
        </div>

        {/* Recalled Memories Summary Card */}
        <div className="bg-[#12192B] border border-gray-800 rounded-lg p-3.5">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] uppercase font-bold text-blue-400 tracking-wider flex items-center space-x-1.5">
              <span>🧠</span>
              <span>Top Recalled Precedents ({investigation.retrieved_memories ? investigation.retrieved_memories.length : 0} Memories)</span>
            </div>
            <span className="text-[10px] font-mono text-gray-400">Bank: team-payments</span>
          </div>

          {(!investigation.retrieved_memories || investigation.retrieved_memories.length === 0) ? (
            <div className="text-xs text-gray-400 italic bg-[#0A0F1A] p-2.5 rounded border border-gray-800/80">
              No prior incident memories recalled (Cold Start or uncharacterized alert signature).
            </div>
          ) : (
            <div className="space-y-1.5">
              {investigation.retrieved_memories.map((mem, idx) => (
                <div key={idx} className="bg-[#0A0F1A] p-2.5 rounded border border-gray-800/80 flex items-start justify-between text-xs font-mono">
                  <div className="flex-1 mr-2">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-blue-400">{mem.id}</span>
                      <span className="text-[10px] px-1.5 py-0.2 bg-emerald-950 text-emerald-400 rounded border border-emerald-800 font-semibold">
                        Score: {typeof mem.score === 'number' ? mem.score.toFixed(3) : mem.score}
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-300 mt-1 font-sans line-clamp-1">
                      {mem.why_matched || mem.text?.slice(0, 80)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Evidence Differential (Matches vs Differences) */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-[#0B1420] border border-emerald-900/50 rounded-lg p-3">
            <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-2 flex items-center space-x-1">
              <span>✓</span>
              <span>Matching Live Signals ({investigation.supporting_evidence.length})</span>
            </div>
            <ul className="space-y-1.5 text-gray-300">
              {investigation.supporting_evidence.map((ev, i) => (
                <li key={i} className="flex items-start space-x-1.5">
                  <span className="text-emerald-500 font-bold mt-0.5">•</span>
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-[#171317] border border-amber-900/50 rounded-lg p-3">
            <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-2 flex items-center space-x-1">
              <span>≠</span>
              <span>Differing Signals / Guardrails</span>
            </div>
            <ul className="space-y-1.5 text-gray-300">
              {investigation.contradicting_evidence.map((ev, i) => (
                <li key={i} className="flex items-start space-x-1.5">
                  <span className="text-amber-500 font-bold mt-0.5">•</span>
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Obsolete Warning Notice (if applicable) */}
        {rec.obsolete_warning && (
          <div className="bg-rose-950/40 border border-rose-600/70 rounded-lg p-3 text-xs text-rose-300 flex items-start space-x-2">
            <span className="text-base mt-0.5">⚠️</span>
            <div>
              <strong className="font-bold">Obsolete Memory Correction:</strong> {rec.obsolete_warning}
            </div>
          </div>
        )}

        {/* Recommendation & Proposed Remediation Steps */}
        <div className="bg-[#12192B] border border-gray-800 rounded-lg p-4">
          <div className="text-[10px] uppercase font-bold text-blue-400 tracking-wider mb-2">
            Proposed Action Steps
          </div>
          <div className="space-y-2">
            {rec.proposed_steps.map((step, idx) => (
              <div key={idx} className="flex items-start space-x-2.5 text-xs text-gray-200">
                <span className="w-5 h-5 rounded-full bg-blue-900/60 text-blue-300 font-bold font-mono text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5 border border-blue-700/40">
                  {idx + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Approval Policy Gate */}
        {rec.approval_required && (
          <div className={`p-3.5 rounded-lg border transition-all ${
            isPolicyApproved 
              ? 'bg-emerald-950/40 border-emerald-600/60 text-emerald-300'
              : 'bg-amber-950/40 border-amber-500/80 text-amber-200 glow-amber'
          }`}>
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-2">
                <span className="text-lg">🛡️</span>
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider">
                    {isPolicyApproved ? 'Approval Policy Satisfied' : 'Approval Gate Required'}
                  </div>
                  <div className="text-xs mt-0.5 text-gray-300">
                    {rec.approval_policy_reason || 'Policy requires engineer sign-off before applying fix.'}
                  </div>
                </div>
              </div>

              {!isPolicyApproved && (
                <button
                  onClick={onApprovePolicy}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-black font-bold text-xs rounded shadow transition-all active:scale-95 whitespace-nowrap"
                >
                  Approve Sign-off
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Action Decision Footer */}
      <div className="p-4 border-t border-gray-800 bg-[#131C31] flex items-center justify-between">
        <div className="text-[11px] text-gray-400">
          Decisions are retained in Hindsight to train future incidents.
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onMarkObsolete}
            className="px-2.5 py-1.5 bg-gray-800 hover:bg-gray-700 text-amber-400 rounded-lg text-xs font-semibold border border-amber-600/40 transition-all flex items-center space-x-1"
            title="Mark historical fix as obsolete due to migration"
          >
            <span>Mark Fix Obsolete</span>
          </button>

          <button
            onClick={onEdit}
            className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-blue-300 rounded-lg text-xs font-semibold border border-blue-600/40 transition-all"
          >
            Edit
          </button>

          <button
            onClick={onReject}
            className="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded-lg text-xs font-semibold border border-rose-700/60 transition-all"
          >
            Reject (Down-weight)
          </button>

          <button
            onClick={onAccept}
            disabled={isApprovalNeeded}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all shadow-md flex items-center space-x-1.5 ${
              isApprovalNeeded
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed opacity-60'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white active:scale-95 glow-emerald'
            }`}
          >
            <span>Accept & Retain</span>
          </button>
        </div>
      </div>
    </div>
  );
}
