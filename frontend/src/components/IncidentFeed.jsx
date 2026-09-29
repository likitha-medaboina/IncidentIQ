import React, { useState } from 'react';

export default function IncidentFeed({ 
  incidents, 
  selectedIncident, 
  onSelectIncident, 
  onRunNext, 
  onSeedStage, 
  currentStage,
  loading 
}) {
  const [filter, setFilter] = useState('');

  const filteredIncidents = incidents.filter(i => 
    i.id.toLowerCase().includes(filter.toLowerCase()) ||
    i.service.toLowerCase().includes(filter.toLowerCase()) ||
    i.alert_text.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="bg-[#0F1626] border border-gray-800 rounded-xl flex flex-col h-full overflow-hidden shadow-xl">
      {/* Header & Quick Action */}
      <div className="p-4 border-b border-gray-800 bg-[#131C31]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
            </span>
            <h2 className="text-sm font-bold tracking-wider uppercase text-gray-200">Incident Feed</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 font-mono">
              {filteredIncidents.length} events
            </span>
          </div>

          <button
            onClick={onRunNext}
            disabled={loading}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all flex items-center space-x-1.5 active:scale-95 disabled:opacity-50"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span>Run Next Incident</span>
          </button>
        </div>

        {/* Stage Selectors */}
        <div className="space-y-1.5">
          <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider">Hindsight Demo Stage</div>
          <div className="grid grid-cols-4 gap-1.5">
            {[
              { stage: 0, label: '0: Cold Start', desc: 'Empty Bank' },
              { stage: 5, label: '5: Deploy OOM', desc: 'Batch Pattern' },
              { stage: 12, label: '12: Disambiguate', desc: 'Traffic Surge' },
              { stage: 20, label: '20: Obsolete Fix', desc: 'Java 21 ZGC' },
            ].map((btn) => (
              <button
                key={btn.stage}
                onClick={() => onSeedStage(btn.stage)}
                disabled={loading}
                className={`py-1 px-1.5 rounded text-left transition-all border ${
                  currentStage === btn.stage
                    ? 'bg-blue-950/80 border-blue-500 text-blue-300 font-bold shadow-sm'
                    : 'bg-[#0B111E] border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                }`}
              >
                <div className="text-[11px] leading-tight truncate">{btn.label}</div>
                <div className="text-[9px] text-gray-400 truncate">{btn.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Filter Input */}
        <div className="mt-3">
          <input
            type="text"
            placeholder="Filter incidents (service, id, alert)..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-[#0A0F1A] border border-gray-800 rounded-lg px-2.5 py-1 text-xs text-gray-200 placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Incidents List */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-800/60 p-2 space-y-1">
        {filteredIncidents.map((inc) => {
          const isSelected = selectedIncident && selectedIncident.id === inc.id;
          const isCritical = inc.severity === 'P1-CRITICAL';

          return (
            <div
              key={inc.id}
              onClick={() => onSelectIncident(inc)}
              className={`p-3 rounded-lg cursor-pointer transition-all border ${
                isSelected
                  ? 'bg-blue-950/40 border-blue-500/70 shadow-md ring-1 ring-blue-500/30'
                  : 'bg-[#0B111E]/80 border-transparent hover:border-gray-800 hover:bg-[#121929]'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs font-bold text-blue-400">{inc.id}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold ${
                  isCritical ? 'bg-red-950/70 text-red-400 border border-red-800/40' : 'bg-amber-950/70 text-amber-400 border border-amber-800/40'
                }`}>
                  {inc.severity}
                </span>
              </div>

              <div className="text-xs font-semibold text-gray-200 mb-1 leading-snug line-clamp-1">
                {inc.alert_text}
              </div>

              <div className="flex items-center justify-between text-[11px] text-gray-400">
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  <span className="font-mono">{inc.service}</span>
                </span>
                <span className="text-[10px] px-1 bg-gray-800/80 rounded text-gray-400 font-mono">SIMULATED</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
