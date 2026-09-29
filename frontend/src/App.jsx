import React, { useState, useEffect } from 'react';
import { api } from './services/api';
import IncidentFeed from './components/IncidentFeed';
import AgentInvestigation from './components/AgentInvestigation';
import MemoryPanel from './components/MemoryPanel';
import BeforeAfterView from './components/BeforeAfterView';
import Scoreboard from './components/Scoreboard';
import ApprovalModal from './components/ApprovalModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' | 'before-after' | 'scoreboard'
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [scoreboardData, setScoreboardData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [currentStage, setCurrentStage] = useState(5);
  const [loading, setLoading] = useState(false);
  const [isPolicyApproved, setIsPolicyApproved] = useState(false);
  const [toast, setToast] = useState(null);
  const [health, setHealth] = useState(null);

  // Modal states
  const [modalConfig, setModalConfig] = useState({ isOpen: false, mode: 'edit', initialText: '' });

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadInitialData = async () => {
    try {
      setLoading(true);
      // Fetch health first so banner reflects live status immediately without waiting for scoreboard eval
      api.getHealth().then(h => setHealth(h)).catch(() => {});

      const [h, incList, pats, time, score] = await Promise.all([
        api.getHealth(),
        api.getIncidents(),
        api.getPatterns(),
        api.getTimeline(),
        api.getScoreboard()
      ]);
      setHealth(h);
      setIncidents(incList);
      setPatterns(pats);
      setTimeline(time);
      setScoreboardData(score);

      // Default select INC-1005 (or first incident)
      if (incList && incList.length > 0) {
        const defaultInc = incList.find(i => i.id === 'INC-1005') || incList[0];
        handleSelectIncident(defaultInc, 5);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
      showToast('Error loading backend data. Make sure FastAPI server is running.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const handleSelectIncident = async (inc, interactionNum = 5) => {
    setSelectedIncident(inc);
    setIsPolicyApproved(false);
    setLoading(true);
    try {
      const inv = await api.investigate(inc, interactionNum);
      setInvestigation(inv);
      // Refresh timeline and patterns
      const [time, pats] = await Promise.all([api.getTimeline(), api.getPatterns()]);
      setTimeline(time);
      setPatterns(pats);
    } catch (err) {
      console.error('Investigation error:', err);
      showToast('Investigation query failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRunNext = () => {
    if (!incidents.length) return;
    const currentIndex = selectedIncident ? incidents.findIndex(i => i.id === selectedIncident.id) : -1;
    const nextIndex = (currentIndex + 1) % incidents.length;
    const nextInc = incidents[nextIndex];
    handleSelectIncident(nextInc, Math.min(nextIndex + 1, 20));
  };

  const handleSeedStage = async (stage) => {
    setLoading(true);
    try {
      await api.seedStage(stage);
      setCurrentStage(stage);
      showToast(`Hindsight memory seeded to Stage ${stage}!`, 'success');
      
      // Refresh memory data
      const [pats, time, h] = await Promise.all([
        api.getPatterns(),
        api.getTimeline(),
        api.getHealth()
      ]);
      setPatterns(pats);
      setTimeline(time);
      setHealth(h);

      // Trigger investigation for the milestone incident corresponding to this stage
      let milestoneId = 'INC-1001';
      if (stage === 5) milestoneId = 'INC-1005';
      if (stage === 12) milestoneId = 'INC-1012';
      if (stage === 20) milestoneId = 'INC-1020';

      const inc = incidents.find(i => i.id === milestoneId) || incidents[0];
      if (inc) {
        handleSelectIncident(inc, stage || 1);
      }
    } catch (err) {
      console.error('Seed error:', err);
      showToast('Failed to seed memory stage', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!selectedIncident || !investigation) return;
    try {
      await api.submitFeedback({
        incidentId: selectedIncident.id,
        action: 'accept',
        editedFix: investigation.recommendation.proposed_steps[0],
        feedback: 'On-call engineer accepted recommendation.',
        engineerName: selectedIncident.engineer_name
      });
      showToast(`Recommendation ACCEPTED & retained into Hindsight bank 'team-payments'!`, 'success');
      const time = await api.getTimeline();
      setTimeline(time);
    } catch (err) {
      showToast('Failed to record acceptance feedback', 'error');
    }
  };

  const handleReject = async () => {
    if (!selectedIncident || !investigation) return;
    try {
      await api.submitFeedback({
        incidentId: selectedIncident.id,
        action: 'reject',
        feedback: 'Recommendation was rejected by engineer; memory down-weighted.',
        engineerName: selectedIncident.engineer_name
      });
      showToast(`Fix REJECTED. Outcome recorded as failed & down-weighted in Hindsight.`, 'warning');
      const time = await api.getTimeline();
      setTimeline(time);
    } catch (err) {
      showToast('Failed to record rejection', 'error');
    }
  };

  const handleEditSubmit = async ({ text, comment }) => {
    if (!selectedIncident) return;
    try {
      await api.submitFeedback({
        incidentId: selectedIncident.id,
        action: 'edit',
        editedFix: text,
        feedback: comment || 'Custom remediation applied by engineer.',
        engineerName: selectedIncident.engineer_name
      });
      showToast(`Custom remediation retained as verified resolution in Hindsight!`, 'success');
      const time = await api.getTimeline();
      setTimeline(time);
    } catch (err) {
      showToast('Failed to save edit feedback', 'error');
    }
  };

  const handleObsoleteSubmit = async ({ text, comment }) => {
    if (!selectedIncident) return;
    try {
      await api.submitFeedback({
        incidentId: selectedIncident.id,
        action: 'edit',
        markAsObsolete: true,
        obsoleteReason: text,
        feedback: comment,
        engineerName: selectedIncident.engineer_name
      });
      showToast(`Memory marked OBSOLETE in Hindsight. Agent will warn & bypass in future.`, 'warning');
      const [time, pats] = await Promise.all([api.getTimeline(), api.getPatterns()]);
      setTimeline(time);
      setPatterns(pats);
    } catch (err) {
      showToast('Failed to mark fix obsolete', 'error');
    }
  };

  const handleTriggerReflect = async () => {
    try {
      const res = await fetch('/api/memory/reflect', { method: 'POST' });
      const data = await res.json();
      setPatterns(data.patterns || []);
      const time = await api.getTimeline();
      setTimeline(time);
      showToast(`Hindsight Reflect consolidated ${data.patterns_count} Learned Patterns!`, 'success');
    } catch (err) {
      showToast('Failed to run reflect', 'error');
    }
  };

  const handleResetBank = async () => {
    if (window.confirm('Reset Hindsight memory bank to empty cold start?')) {
      try {
        await api.resetBank();
        setCurrentStage(0);
        showToast('Memory bank reset to clean cold start.', 'info');
        loadInitialData();
      } catch (err) {
        showToast('Failed to reset memory bank', 'error');
      }
    }
  };

  const handleRunBeforeAfter = async () => {
    if (!selectedIncident) return;
    setLoading(true);
    try {
      const data = await api.compareBeforeAfter(selectedIncident, currentStage || 5);
      setComparisonData(data);
      showToast('Side-by-side evaluation completed!', 'success');
    } catch (err) {
      showToast('Failed to run comparison', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090D16] text-gray-100 flex flex-col font-sans">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-2xl text-xs font-semibold flex items-center space-x-2 border transition-all animate-bounce ${
          toast.type === 'success'
            ? 'bg-emerald-950 text-emerald-200 border-emerald-600'
            : toast.type === 'warning'
            ? 'bg-amber-950 text-amber-200 border-amber-600'
            : toast.type === 'error'
            ? 'bg-rose-950 text-rose-200 border-rose-600'
            : 'bg-blue-950 text-blue-200 border-blue-600'
        }`}>
          <span>{toast.type === 'success' ? '✓' : '⚠️'}</span>
          <span>{toast.message}</span>
        </div>
      )}

      {/* Top Header Navigation */}
      <header className="border-b border-gray-800 bg-[#0C1220]/95 backdrop-blur-md sticky top-0 z-30 px-6 py-3">
        <div className="flex items-center justify-between">
          {/* Logo & Tagline */}
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-md text-base">
              ⚡
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base font-extrabold tracking-tight text-white">IncidentIQ</h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-400 font-mono font-bold border border-blue-800/60">
                  HINDSIGHT POWERED
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 font-mono border border-purple-800/60">
                  SIMULATED FINTECH CLUSTER
                </span>
              </div>
              <div className="text-[11px] text-gray-400">
                Self-Learning DevOps Incident Response Agent (Interactions 1 → 5 → 20)
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center bg-[#070B13] p-1 rounded-xl border border-gray-800">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Triage Dashboard
            </button>
            <button
              onClick={() => {
                setActiveTab('before-after');
                if (!comparisonData) handleRunBeforeAfter();
              }}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'before-after'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Before / After Mode
            </button>
            <button
              onClick={() => setActiveTab('scoreboard')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'scoreboard'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Learning Scoreboard
            </button>
          </div>

          {/* Hindsight Bank Indicator & Fallback status */}
          <div className="flex items-center space-x-2 text-xs font-mono">
            <div className="bg-[#070B13] px-3 py-1.5 rounded-lg border border-gray-800 flex items-center space-x-2">
              <span className={`w-2 h-2 rounded-full ${health?.hindsight_live_connected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
              <span className="text-gray-400 text-[11px]">Bank:</span>
              <span className="font-bold text-blue-400">team-payments</span>
            </div>
            <div className={`px-2.5 py-1.5 rounded-lg border text-[10px] font-bold flex items-center space-x-1.5 ${
              health?.hindsight_live_connected 
                ? 'bg-emerald-950/80 border-emerald-700 text-emerald-300' 
                : 'bg-amber-950/80 border-amber-700/80 text-amber-300'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.hindsight_live_connected ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
              <span>{health?.hindsight_live_connected ? 'LIVE HINDSIGHT SERVER (PRIMARY)' : 'FALLBACK: EMBEDDED HINDSIGHT ENGINE'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 overflow-hidden">
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-12 gap-5 h-[calc(100vh-115px)]">
            {/* Panel 1: Incident Feed (col-span-3) */}
            <div className="col-span-3 h-full">
              <IncidentFeed
                incidents={incidents}
                selectedIncident={selectedIncident}
                onSelectIncident={(inc) => handleSelectIncident(inc, currentStage || 5)}
                onRunNext={handleRunNext}
                onSeedStage={handleSeedStage}
                currentStage={currentStage}
                loading={loading}
              />
            </div>

            {/* Panel 2: Agent Investigation (col-span-5) */}
            <div className="col-span-5 h-full">
              <AgentInvestigation
                incident={selectedIncident}
                investigation={investigation}
                loading={loading}
                onAccept={handleAccept}
                onReject={handleReject}
                onEdit={() => setModalConfig({
                  isOpen: true,
                  mode: 'edit',
                  initialText: investigation?.recommendation?.proposed_steps?.join('\n') || ''
                })}
                onMarkObsolete={() => setModalConfig({
                  isOpen: true,
                  mode: 'obsolete',
                  initialText: 'Fix is obsolete due to platform upgrade to Java 21 ZGC / KEDA autoscaling'
                })}
                onApprovePolicy={() => {
                  setIsPolicyApproved(true);
                  showToast('Production rollback sign-off granted by On-Call Lead!', 'success');
                }}
                isPolicyApproved={isPolicyApproved}
              />
            </div>

            {/* Panel 3: Hindsight Memory Panel (col-span-4) */}
            <div className="col-span-4 h-full">
              <MemoryPanel
                retrievedMemories={investigation?.retrieved_memories || []}
                patterns={patterns}
                timeline={timeline}
                bankId="team-payments"
                isLiveConnected={health?.hindsight_live_connected || false}
                onTriggerReflect={handleTriggerReflect}
                onResetBank={handleResetBank}
              />
            </div>
          </div>
        )}

        {activeTab === 'before-after' && (
          <div className="h-[calc(100vh-115px)] overflow-y-auto">
            <BeforeAfterView
              incident={selectedIncident}
              comparisonData={comparisonData}
              onRunComparison={handleRunBeforeAfter}
              loading={loading}
            />
          </div>
        )}

        {activeTab === 'scoreboard' && (
          <div className="h-[calc(100vh-115px)] overflow-y-auto">
            <Scoreboard scoreboardData={scoreboardData} />
          </div>
        )}
      </main>

      {/* Modal Dialog */}
      <ApprovalModal
        isOpen={modalConfig.isOpen}
        mode={modalConfig.mode}
        initialText={modalConfig.initialText}
        onClose={() => setModalConfig({ ...modalConfig, isOpen: false })}
        onSubmit={modalConfig.mode === 'edit' ? handleEditSubmit : handleObsoleteSubmit}
      />
    </div>
  );
}
