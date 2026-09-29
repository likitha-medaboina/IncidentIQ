import React, { useState } from 'react';

export default function MemoryPanel({ 
  retrievedMemories, 
  patterns, 
  timeline, 
  bankId = 'team-payments',
  isLiveConnected = false,
  onTriggerReflect,
  onResetBank
}) {
  const [activeTab, setActiveTab] = useState('recalled'); // 'recalled' | 'patterns' | 'timeline'

  return (
    <div className="bg-[#0F1626] border border-gray-800 rounded-xl flex flex-col h-full overflow-hidden shadow-xl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-[#131C31]">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-blue-400 font-bold text-sm">🧠</span>
            <h2 className="text-sm font-bold tracking-wider uppercase text-gray-200">
              Hindsight Memory Engine
            </h2>
          </div>

          <div className="flex items-center space-x-2">
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold flex items-center space-x-1 ${
              isLiveConnected 
                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                : 'bg-amber-950 text-amber-300 border border-amber-800'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isLiveConnected ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
              <span>{isLiveConnected ? 'Live Hindsight Server (Primary)' : 'Fallback: Embedded Engine'}</span>
            </span>

            <button
              onClick={onResetBank}
              title="Reset memory bank to cold start"
              className="text-[10px] px-2 py-0.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 transition-all font-mono"
            >
              Reset Bank
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
          <span className="font-mono">Bank: <strong className="text-blue-300">{bankId}</strong></span>
          <span className="text-[11px] text-gray-400">Multi-strategy RAG + Reflect</span>
        </div>

        {/* Tab navigation */}
        <div className="flex border-b border-gray-800 -mb-4 space-x-4">
          <button
            onClick={() => setActiveTab('recalled')}
            className={`pb-2 text-xs font-semibold tracking-wide transition-all border-b-2 flex items-center space-x-1 ${
              activeTab === 'recalled'
                ? 'border-blue-500 text-blue-400 font-bold'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            <span>Recall Results</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-950 text-blue-300 font-mono">
              {retrievedMemories.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('patterns')}
            className={`pb-2 text-xs font-semibold tracking-wide transition-all border-b-2 flex items-center space-x-1 ${
              activeTab === 'patterns'
                ? 'border-blue-500 text-blue-400 font-bold'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            <span>Learned Patterns</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-purple-950 text-purple-300 font-mono">
              {patterns.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('timeline')}
            className={`pb-2 text-xs font-semibold tracking-wide transition-all border-b-2 flex items-center space-x-1 ${
              activeTab === 'timeline'
                ? 'border-blue-500 text-blue-400 font-bold'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            <span>Audit Timeline</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-gray-800 text-gray-400 font-mono">
              {timeline.length}
            </span>
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* TAB 1: RECALL RESULTS */}
        {activeTab === 'recalled' && (
          <div>
            {retrievedMemories.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-xs">
                <div className="text-xl mb-1">📭</div>
                <div className="font-semibold text-gray-300">No Memories Recalled</div>
                <div className="mt-1 text-gray-400">
                  Either this is a Cold Start interaction or no past incidents match the live error signature.
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {retrievedMemories.map((mem) => {
                  const isObsolete = mem.is_obsolete;
                  const isFailed = mem.outcome === 'failed';

                  return (
                    <div
                      key={mem.id}
                      className={`p-3 rounded-lg border text-xs transition-all ${
                        isObsolete
                          ? 'bg-rose-950/20 border-rose-800/50'
                          : isFailed
                          ? 'bg-amber-950/20 border-amber-800/40'
                          : 'bg-[#12192B] border-gray-800 hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center space-x-1.5">
                          <span className="font-mono font-bold text-blue-400">{mem.id}</span>
                          {isObsolete && (
                            <span className="px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-300 font-mono text-[10px] font-bold border border-rose-700/60">
                              OBSOLETE FIX
                            </span>
                          )}
                          {isFailed && !isObsolete && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-300 font-mono text-[10px] font-bold border border-amber-700/60">
                              DOWN-WEIGHTED
                            </span>
                          )}
                        </div>

                        <div className="flex items-center space-x-1 text-gray-400 text-[11px] font-mono">
                          <span>Relevance:</span>
                          <span className="font-bold text-emerald-400">
                            {typeof mem.score === 'number' ? mem.score.toFixed(2) : mem.score}
                          </span>
                        </div>
                      </div>

                      {/* Why Matched Breakdown */}
                      <div className="bg-black/30 p-2 rounded border border-gray-800/60 mb-2 font-mono text-[11px] text-blue-300/90">
                        <span className="text-gray-400">Match Vector: </span>
                        {mem.why_matched}
                      </div>

                      {/* Obsolete Reason */}
                      {isObsolete && mem.obsolete_reason && (
                        <div className="text-[11px] text-rose-300 mb-1.5 font-medium">
                          ⛔ <strong>Deprecation Note:</strong> {mem.obsolete_reason}
                        </div>
                      )}

                      {/* Memory Content Text */}
                      <div className="text-gray-300 text-[11px] leading-relaxed line-clamp-3 font-mono bg-[#090D16] p-2 rounded border border-gray-900">
                        {mem.text}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: LEARNED PATTERNS (REFLECT) */}
        {activeTab === 'patterns' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[11px] text-gray-400">
                Cross-incident synthesis generated via <code className="text-purple-300">Hindsight.reflect()</code>
              </div>
              <button
                onClick={onTriggerReflect}
                className="px-2 py-1 bg-purple-900/60 hover:bg-purple-800 text-purple-200 rounded text-[10px] font-bold border border-purple-700/60 transition-all flex items-center space-x-1"
              >
                <span>⚡ Re-run Reflect</span>
              </button>
            </div>

            {patterns.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-xs">
                <div className="text-xl mb-1">🔍</div>
                <div className="font-semibold text-gray-300">No Cross-Incident Patterns Yet</div>
                <div className="mt-1 text-gray-400">
                  Reflect generates patterns after multiple incidents (e.g. Stage 5, 12, or 20). Click "Re-run Reflect" to trigger reasoning.
                </div>
              </div>
            ) : (
              patterns.map((p) => (
                <div
                  key={p.id}
                  className="p-3.5 rounded-lg border border-purple-900/50 bg-[#161224] text-xs space-y-2 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-purple-400 text-[11px]">{p.id}</span>
                    <span className="px-1.5 py-0.2 bg-purple-950 text-purple-300 rounded text-[10px] font-mono font-bold border border-purple-800">
                      {p.confidence} CONFIDENCE
                    </span>
                  </div>

                  <div className="font-semibold text-gray-200 text-xs leading-snug">
                    {p.pattern}
                  </div>

                  <div className="bg-black/30 p-2 rounded border border-purple-950 text-[11px] text-purple-300">
                    <strong className="text-gray-400">Prescription: </strong>
                    {p.recommendation}
                  </div>

                  <div className="text-[10px] text-gray-400 font-mono">
                    Synthesized from evidence incidents: {p.evidence_incident_ids.join(', ')}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 3: AUDIT TIMELINE */}
        {activeTab === 'timeline' && (
          <div className="space-y-2">
            <div className="text-[11px] text-gray-400 mb-2">
              Real-time audit log of Hindsight Retain, Recall, and Reflect operations:
            </div>

            {timeline.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-xs">
                No memory calls recorded yet.
              </div>
            ) : (
              timeline.slice(0, 25).map((evt) => {
                const isRetain = evt.operation === 'RETAIN';
                const isRecall = evt.operation === 'RECALL';
                const isReflect = evt.operation === 'REFLECT';

                return (
                  <div
                    key={evt.id}
                    className="p-2.5 rounded-lg border border-gray-800/80 bg-[#0B111E] text-xs font-mono space-y-1"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                        isRetain 
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          : isRecall
                          ? 'bg-blue-950 text-blue-400 border border-blue-800'
                          : 'bg-purple-950 text-purple-400 border border-purple-800'
                      }`}>
                        {evt.operation}
                      </span>
                      <span className="text-gray-400 text-[10px]">{evt.latency_ms}ms</span>
                    </div>

                    <div className="text-gray-300 text-[11px] truncate">
                      {evt.query_or_summary}
                    </div>

                    {evt.matched_ids && evt.matched_ids.length > 0 && (
                      <div className="text-[10px] text-gray-400">
                        Matches: {evt.matched_ids.join(', ')}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}
