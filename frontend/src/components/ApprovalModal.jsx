import React, { useState } from 'react';

export default function ApprovalModal({ isOpen, mode, initialText, onClose, onSubmit }) {
  const [text, setText] = useState(initialText || '');
  const [comment, setComment] = useState('');

  if (!isOpen) return null;

  const isEdit = mode === 'edit';

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ text, comment });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="bg-[#0F1626] border border-gray-700 rounded-xl max-w-lg w-full p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <h3 className="text-sm font-bold text-gray-100 flex items-center space-x-2">
            <span>{isEdit ? '✏️ Edit Remediation Steps' : '⚠️ Mark Historical Fix as Obsolete'}</span>
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-lg leading-none"
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {isEdit ? (
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">
                Custom Remediation Plan
              </label>
              <textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Modify steps before applying and retaining..."
                className="w-full bg-[#0A0F1A] border border-gray-800 rounded-lg p-2.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500 font-mono"
                required
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-rose-300 mb-1">
                Reason for Obsolescence (e.g. Platform Migration, Architecture Change)
              </label>
              <textarea
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Explain why this historical fix is deprecated so the agent stops recommending it..."
                className="w-full bg-[#0A0F1A] border border-rose-900/60 rounded-lg p-2.5 text-xs text-gray-200 focus:outline-none focus:border-rose-500 font-mono"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">
              Engineer Notes / Rationale
            </label>
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g. Verified with Platform Lead; prevents crash loop"
              className="w-full bg-[#0A0F1A] border border-gray-800 rounded-lg p-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-gray-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`px-4 py-1.5 text-white text-xs rounded-lg font-bold shadow-md transition-all active:scale-95 ${
                isEdit ? 'bg-blue-600 hover:bg-blue-500' : 'bg-rose-600 hover:bg-rose-500'
              }`}
            >
              {isEdit ? 'Save & Retain Fix' : 'Confirm Obsolescence'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
