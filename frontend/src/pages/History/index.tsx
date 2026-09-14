import React, { useState, useEffect } from 'react';

interface ToolStep {
  tool_name: string;
  status: string;
  summary: any;
  log_download_url: string | null;
}

export default function RunHistoryDetailsModal({ runId, onClose }: { runId: number; onClose: () => void }) {
  const [loading, setLoading] = useState(true);
  const [runDetails, setRunDetails] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<string>('');
  const [rawLogs, setRawLogs] = useState<string>('');
  const [logsLoading, setLogsLoading] = useState(false);

  // Fetch the light framework metadata tree when opening the modal
  useEffect(() => {
    fetch(`${import.meta.env.VITE_DJANGO_BACKEND_URL}/api/workflow-runs/${runId}/`)
      .then(res => res.json())
      .then(data => {
        setRunDetails(data);
        if (data.steps?.length > 0) {
          setActiveTab(data.steps[0].tool_name); // Auto-focus first tool tab
        }
        setLoading(false);
      });
  }, [runId]);

  // Fetch the heavy terminal text content ONLY when switching tabs!
  useEffect(() => {
    if (!activeTab || !runDetails) return;
    
    const currentStep = runDetails.steps.find((s: ToolStep) => s.tool_name === activeTab);
    if (!currentStep || !currentStep.log_download_url) {
      setRawLogs("No logs recorded for this tool framework step.");
      return;
    }

    setLogsLoading(true);
    // Fetch directly from Cloudflare R2 via the presigned URL! 0% Django server strain.
    fetch(currentStep.log_download_url)
      .then(res => res.text())
      .then(text => {
        setRawLogs(text);
        setLogsLoading(false);
      })
      .catch(() => {
        setRawLogs("❌ Error pulling logs down from cloud storage.");
        setLogsLoading(false);
      });
  }, [activeTab, runDetails]);

  if (loading) return <div className="p-6 text-center text-slate-500">Loading Run Context...</div>;

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl">
        
        {/* Header Block */}
        <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 rounded-t-2xl">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Execution Diagnostics: Run #{runId}</h2>
            <p className="text-xs text-slate-500">Status: <span className="font-semibold uppercase">{runDetails.status}</span></p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-sm cursor-pointer">✕ Close</button>
        </div>

        {/* Tab Navigation Array */}
        <div className="flex bg-slate-100 p-1.5 gap-1 m-4 rounded-xl">
          {runDetails.steps.map((step: ToolStep) => (
            <button
              key={step.tool_name}
              onClick={() => setActiveTab(step.tool_name)}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                activeTab === step.tool_name 
                  ? 'bg-white text-slate-900 shadow-sm' 
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {step.tool_name.toUpperCase()} ({step.status === 'success' ? '✅' : '❌'})
            </button>
          ))}
        </div>

        {/* Live Code Console Window Component */}
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          <div className="bg-slate-950 text-slate-200 font-mono text-xs p-4 rounded-xl shadow-inner min-h-[300px] max-h-[500px] overflow-auto whitespace-pre">
            {logsLoading ? (
              <p className="text-slate-400 animate-pulse">// Streaming log lines down from bucket storage layer...</p>
            ) : (
              <code>{rawLogs}</code>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
