import React, { useState } from 'react';

export default function BeforeAfterView({ incident, onRunComparison, comparisonData, loading }) {
  if (loading) {
    return (
      <div className="bg-[#0F1626] border border-gray-800 rounded-xl p-12 flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <div className="text-base font-bold text-gray-200">Running Side-by-Side Triage Comparison...</div>
        <div className="text-xs text-gray-400 mt-1">Executing live alert against an Empty Memory Bank vs Trained Memory Bank.</div>
      </div>
    );
  }

  if (!comparisonData) {
    return (
      <div className="bg-[#0F1626] border border-gray-800 rounded-xl p-12 flex flex-col items-center justify-center text-center">
        <div className="text-3xl mb-3">⚡</div>
        <h3 className="text-base font-bold text-gray-200">Before & After Hindsight Benchmark</h3>
        <p className="text-xs text-gray-400 mt-1 max-w-md">
          Evaluate how the agent performs on this exact incident with an <strong className="text-gray-300">Empty Memory Bank</strong> (Interaction 1 cold start) versus a <strong className="text-blue-400">Trained Memory Bank</strong> with Hindsight.
        </p>
        <button
          onClick={onRunComparison}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-lg transition-all active:scale-95"
        >
          Run Side-by-Side Evaluation
        </button>
      </div>
    );
  }

  const { before, after, improvement_highlights } = comparisonData;

  return (
    <div className="space-y-4">
      {/* Top Value Banner */}
      <div className="bg-gradient-to-r from-blue-950/80 via-[#131C31] to-purple-950/80 border border-blue-600/40 rounded-xl p-4 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider font-mono">Value Proof</span>
            <h3 className="text-sm font-bold text-gray-100 mt-0.5">
              Hindsight Memory Impact on Incident Triage
            </h3>
          </div>
          <button
            onClick={onRunComparison}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded border border-gray-700 font-semibold"
          >
            Re-run Comparison
          </button>
        </div>

        <div className="grid grid-cols-4 gap-3 mt-3 pt-3 border-t border-gray-800/80">
          {improvement_highlights.map((highlight, idx) => (
            <div key={idx} className="bg-black/30 p-2 rounded border border-gray-800 text-[11px] text-gray-200 flex items-center space-x-1.5">
              <span className="text-emerald-400 font-bold">✓</span>
              <span>{highlight}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Side by side columns */}
      <div className="grid grid-cols-2 gap-4">
        {/* LEFT: COLD START (BEFORE) */}
        <div className="bg-[#0F1626] border border-gray-800/80 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-gray-800 pb-2.5">
            <div>
              <div className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Baseline</div>
              <h4 className="text-sm font-bold text-gray-300">Cold Start (Empty Memory Bank)</h4>
            </div>
            <span className="px-2 py-0.5 bg-gray-800 text-gray-400 text-xs font-mono font-bold rounded">
              {before.confidence} CONFIDENCE
            </span>
          </div>

          <div className="bg-[#0B111E] p-3 rounded-lg border border-gray-900 text-xs space-y-1">
            <div className="text-[10px] font-bold text-gray-400 uppercase">Hypothesis</div>
            <div className="text-gray-300 leading-snug">{before.hypothesis}</div>
          </div>

          <div className="bg-[#0B111E] p-3 rounded-lg border border-gray-900 text-xs space-y-1">
            <div className="text-[10px] font-bold text-gray-400 uppercase">Hindsight Recall</div>
            <div className="text-gray-400 italic">0 memories retrieved (agent has no prior operational context)</div>
          </div>

          <div className="bg-[#0B111E] p-3 rounded-lg border border-gray-900 text-xs space-y-1.5">
            <div className="text-[10px] font-bold text-gray-400 uppercase">Proposed Action Steps</div>
            {before.proposed_steps.map((step, i) => (
              <div key={i} className="text-gray-300 text-[11px] flex items-start space-x-1.5">
                <span className="text-gray-400 font-mono">•</span>
                <span>{step}</span>
              </div>
            ))}
          </div>

          <div className="p-2.5 rounded bg-gray-900/40 border border-gray-800 text-[11px] text-gray-400">
            <strong>Outcome:</strong> Requires 50+ minutes of manual on-call debugging, heap dump extraction, and trial-and-error container restarts.
          </div>
        </div>

        {/* RIGHT: TRAINED BANK (AFTER) */}
        <div className="bg-[#0F1626] border border-blue-600/50 rounded-xl p-4 space-y-3 shadow-lg ring-1 ring-blue-500/20">
          <div className="flex items-center justify-between border-b border-gray-800 pb-2.5">
            <div>
              <div className="text-[10px] uppercase font-bold text-blue-400 tracking-wider">Hindsight Augmented</div>
              <h4 className="text-sm font-bold text-blue-200">Trained Bank (Interaction 5-20)</h4>
            </div>
            <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-700/60 text-xs font-mono font-bold rounded">
              {after.confidence} CONFIDENCE
            </span>
          </div>

          <div className="bg-[#12192B] p-3 rounded-lg border border-blue-900/40 text-xs space-y-1">
            <div className="text-[10px] font-bold text-blue-400 uppercase">Hypothesis</div>
            <div className="text-gray-100 font-semibold leading-snug">{after.hypothesis}</div>
          </div>

          <div className="bg-[#12192B] p-3 rounded-lg border border-blue-900/40 text-xs space-y-1">
            <div className="text-[10px] font-bold text-blue-400 uppercase">Hindsight Recall</div>
            <div className="text-gray-200 text-[11px]">
              Recalled <strong>{after.retrieved_memories.length} past incidents</strong>: {after.retrieved_memories.map(m => m.id).join(', ')}
            </div>
          </div>

          <div className="bg-[#12192B] p-3 rounded-lg border border-blue-900/40 text-xs space-y-1.5">
            <div className="text-[10px] font-bold text-blue-400 uppercase">Proposed Action Steps</div>
            {after.proposed_steps.map((step, i) => (
              <div key={i} className="text-gray-200 text-[11px] flex items-start space-x-1.5">
                <span className="text-emerald-400 font-bold">✓</span>
                <span className="font-medium">{step}</span>
              </div>
            ))}
          </div>

          <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-800/60 text-[11px] text-emerald-300">
            <strong>Outcome:</strong> Root cause diagnosed in {after.execution_time_ms}ms with precise configuration remediation and team policy compliance.
          </div>
        </div>
      </div>
    </div>
  );
}
