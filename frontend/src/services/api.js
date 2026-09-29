const BASE_URL = '/api';

export const api = {
  async getHealth() {
    const res = await fetch(`${BASE_URL}/health`);
    return res.json();
  },

  async getIncidents() {
    const res = await fetch(`${BASE_URL}/incidents`);
    return res.json();
  },

  async getIncident(id) {
    const res = await fetch(`${BASE_URL}/incidents/${id}`);
    return res.json();
  },

  async investigate(incident, interactionNumber = 1) {
    const res = await fetch(`${BASE_URL}/investigate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident,
        interaction_number: interactionNumber
      })
    });
    return res.json();
  },

  async compareBeforeAfter(incident, interactionNumber = 5) {
    const res = await fetch(`${BASE_URL}/investigate/before-after`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident,
        interaction_number: interactionNumber
      })
    });
    return res.json();
  },

  async submitFeedback({ incidentId, action, editedFix, feedback, markAsObsolete, obsoleteReason, engineerName }) {
    const res = await fetch(`${BASE_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident_id: incidentId,
        action,
        edited_fix: editedFix,
        engineer_feedback: feedback,
        mark_as_obsolete: markAsObsolete || false,
        obsolete_reason: obsoleteReason,
        engineer_name: engineerName || 'oncall-devops'
      })
    });
    return res.json();
  },

  async getTimeline() {
    const res = await fetch(`${BASE_URL}/memory/timeline`);
    return res.json();
  },

  async getPatterns() {
    const res = await fetch(`${BASE_URL}/memory/patterns`);
    return res.json();
  },

  async getPolicies() {
    const res = await fetch(`${BASE_URL}/memory/policies`);
    return res.json();
  },

  async seedStage(stage) {
    const res = await fetch(`${BASE_URL}/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage })
    });
    return res.json();
  },

  async resetBank() {
    const res = await fetch(`${BASE_URL}/memory/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bank_id: 'team-payments' })
    });
    return res.json();
  },

  async getScoreboard() {
    const res = await fetch(`${BASE_URL}/scoreboard`);
    return res.json();
  }
};
