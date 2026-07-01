import React, { useState, useEffect, useRef } from "react";
import { useSocketStore } from "@/features/store/selectionStore";
import { Terminal, Shield, Trash2, ArrowDown, Loader2 } from "lucide-react";

export default function LiveTerminal() {
  const [visibleLines, setVisibleLines] = useState<string[]>([]);
  const [autoscroll, setAutoscroll] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  
  // 🎯 REAL-TIME LOADER STATES
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [pipelineFinished, setPipelineFinished] = useState(false);

  const logQueue = useRef<string[]>([]);
  const currentLineText = useRef<string>("");
  const currentCharIndex = useRef<number>(0);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);
  const engineTimerRef = useRef<NodeJS.Timeout | null>(null);

  // ✅ Listen to global streaming data from store
  const streamingMessage = useSocketStore((state) => state.streamingMessage);

  useEffect(() => {
    console.log("🎯 Dashboard caught streaming packet:", streamingMessage);
    if (streamingMessage?.message?.stream_type === "live_logs") {
      const lineBatch = streamingMessage.message.data;
      const currentRunningTool = streamingMessage.message.tool;
      const executionDoneMarker = streamingMessage.message.is_complete;

      if (currentRunningTool) {
        setActiveTool(currentRunningTool);
        setPipelineFinished(executionDoneMarker);
      }

      if (Array.isArray(lineBatch)) {
        logQueue.current.push(...lineBatch);
        if (!isTyping) setIsTyping(true);
      }
    }
  }, [streamingMessage]);

  // Typewriter Loop Engine Block
  useEffect(() => {
    if (!isTyping) return;

    const typeCharacter = () => {
      if (currentCharIndex.current >= currentLineText.current.length) {
        if (logQueue.current.length > 0) {
          currentLineText.current = logQueue.current.shift()!;
          currentCharIndex.current = 0;
          setVisibleLines((prev) => [...prev, ""]);
        } else {
          setIsTyping(false);
          return;
        }
      }

      const nextChar = currentLineText.current.charAt(currentCharIndex.current);
      currentCharIndex.current += 1;

      setVisibleLines((prev) => {
        if (prev.length === 0) return [nextChar];
        const updated = [...prev];
        updated[updated.length - 1] = updated[updated.length - 1] + nextChar;
        return updated;
      });

      const optimalSpeed = logQueue.current.length > 50 ? 1 : 12;
      engineTimerRef.current = setTimeout(typeCharacter, optimalSpeed);
    };

    engineTimerRef.current = setTimeout(typeCharacter, 12);
    return () => {
      if (engineTimerRef.current) clearTimeout(engineTimerRef.current);
    };
  }, [isTyping]);

  // Autoscroll View Anchor Shifts
  useEffect(() => {
    if (autoscroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "auto" });
    }
  }, [visibleLines, autoscroll]);

  const handleClear = () => {
    logQueue.current = [];
    currentLineText.current = "";
    currentCharIndex.current = 0;
    setVisibleLines([]);
    setIsTyping(false);
    setActiveTool(null);
    setPipelineFinished(false);
  };

  return (
    <div className="w-full bg-[#09090b] border border-[#1f1f23] rounded-xl shadow-2xl overflow-hidden flex flex-col h-[500px]">
      
      {/* Terminal Top Action Menu Header */}
      <div className="bg-[#121215] px-4 py-3 border-b border-[#1f1f23] flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-purple-400" />
          <span className="font-mono text-xs text-gray-400 tracking-wider font-bold">
            ODOZI SUITE SCANNERS TERMINAL
          </span>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoscroll(!autoscroll)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono border transition-all ${
              autoscroll 
                ? "bg-purple-500/10 text-purple-400 border-purple-500/20" 
                : "bg-zinc-800 text-zinc-400 border-zinc-700"
            }`}
          >
            <ArrowDown className={`w-3 h-3 ${autoscroll ? "animate-bounce" : ""}`} />
            {autoscroll ? "AUTOSCROLL" : "LOCKED"}
          </button>

          <button
            onClick={handleClear}
            className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded hover:bg-zinc-800"
            title="Flush Local Console Display"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Screen Ingestion Viewport Grid */}
      <div className="flex-grow p-5 overflow-y-auto font-mono text-[13px] leading-relaxed text-zinc-300 space-y-1 select-text scrollbar-thin scrollbar-thumb-zinc-800">
        {visibleLines.length === 0 && !activeTool && (
          <div className="h-full flex flex-col items-center justify-center gap-2 text-zinc-600">
            <Shield className="w-5 h-5 text-zinc-700 animate-pulse" />
            <p className="text-xs">Awaiting workflow compilation data chunks from GitHub...</p>
          </div>
        )}
        
        {visibleLines.map((line, index) => {
          let lineClass = "text-zinc-300";
          
          // Style tool demarcations distinctly 
          if (line.startsWith("┌──") || line.startsWith("│") || line.startsWith("└──")) {
            lineClass = "text-purple-400 font-bold bg-purple-500/5 px-2 tracking-wide block border-l-2 border-purple-500";
          }
          else if (line.includes("Error:") || line.includes("FAILED") || line.includes("Traceback")) {
            lineClass = "text-red-400 bg-red-500/5 px-1.5 rounded block font-semibold";
          }
          else if (line.includes("PASSED") || line.includes("SUCCESS")) {
            lineClass = "text-emerald-400 font-bold";
          }
          else if (line.includes("WARNING") || line.includes("Warning:")) {
            lineClass = "text-amber-500";
          }

          return (
            <div key={index} className={`whitespace-pre-wrap ${lineClass}`}>
              {line}
            </div>
          );
        })}

        {/* 🎯 THE STREAMING LOADER WIDGET CONTAINER CARD */}
        {activeTool && !pipelineFinished && !isTyping && (
          <div className="flex items-center gap-3 p-3 bg-zinc-900/40 border border-zinc-800 rounded-lg my-4 max-w-md animate-pulse">
            <Loader2 className="w-4 h-4 text-purple-400 animate-spin flex-shrink-0" />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-purple-400">
                [ RUNNING COMPILATION ]: {activeTool.toUpperCase()} UTILITIES ACTIVE
              </span>
              <span className="text-[11px] text-zinc-500">
                Background thread testing ongoing over cloud runner...
              </span>
            </div>
          </div>
        )}
        
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
