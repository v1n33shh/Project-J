import { useState, useEffect, useRef } from "react";
import "./App.css";

// Global Audio Context and Queue for TTS Streaming
const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 64; // Small size for smooth chunky neon bars
analyser.connect(audioCtx.destination);
const dataArray = new Uint8Array(analyser.frequencyBinCount);

let audioQueue: { buffer: Float32Array, sampleRate: number }[] = [];
let isPlaying = false;
let currentSource: AudioBufferSourceNode | null = null;

const playNextAudio = () => {
    if (audioQueue.length === 0) {
        isPlaying = false;
        currentSource = null;
        return;
    }
    isPlaying = true;
    const { buffer, sampleRate } = audioQueue.shift()!;
    
    const source = audioCtx.createBufferSource();
    const audioBuffer = audioCtx.createBuffer(1, buffer.length, sampleRate);
    audioBuffer.getChannelData(0).set(buffer);
    
    source.buffer = audioBuffer;
    source.connect(analyser); // Connect to analyser instead of destination
    source.onended = () => {
        playNextAudio();
    };
    source.start();
    currentSource = source;
};

const stopAudio = () => {
    audioQueue = [];
    if (currentSource) {
        try { currentSource.stop(); } catch (e) {}
        currentSource = null;
    }
    isPlaying = false;
};

function App() {
  const [input, setInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: 'user'|'jarvis', text: string}[]>([
    { role: 'jarvis', text: 'System initialized. Awaiting input.' }
  ]);
  
  const [feed, setFeed] = useState<{id: number, type: 'log'|'signal'|'action', text: string}[]>([
    { id: 1, type: 'log', text: '[SYSTEM] Core OS Boot Sequence Complete' },
    { id: 2, type: 'signal', text: '[MEMORY] Synchronizing local Qdrant vectors...' },
    { id: 3, type: 'action', text: '[AGENT] Planner module loaded and standing by.' },
  ]);

  const endOfChatRef = useRef<HTMLDivElement>(null);

  const [isProcessing, setIsProcessing] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Audio Visualizer Loop
  useEffect(() => {
    let animationId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      animationId = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / dataArray.length);
      let x = 0;

      for (let i = 0; i < dataArray.length; i++) {
        // Map 0-255 to canvas height
        const val = dataArray[i];
        const barHeight = (val / 255) * canvas.height;
        
        // Add glowing cyan color
        const glowIntensity = Math.min(255, 100 + val);
        ctx.fillStyle = `rgba(0, ${glowIntensity}, 255, ${val > 0 ? 0.8 : 0.1})`;
        
        ctx.fillRect(x, canvas.height - barHeight, barWidth - 2, barHeight);
        x += barWidth;
      }
    };
    draw();

    return () => cancelAnimationFrame(animationId);
  }, []);

  useEffect(() => {
    let socket: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connectWS = () => {
      socket = new WebSocket("ws://localhost:8765");
      
      socket.onopen = () => {
        console.log("Connected to Jarvis Backend");
        setIsConnected(true);
        setFeed(prev => [...prev, { id: Date.now(), type: 'log', text: '[SYSTEM] WebSocket Connected to Backend' }]);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const { type, payload } = data;

          if (type === "agent_step") {
            setIsProcessing(true);
            setFeed(prev => [...prev, { id: Date.now(), type: 'signal', text: `[AGENT] ${payload.message}` }]);
          } 
          else if (type === "tool_execution_start") {
            setFeed(prev => [...prev, { id: Date.now(), type: 'action', text: `[TOOL] Executing: ${payload.tool}` }]);
          }
          else if (type === "tool_execution_result") {
            setFeed(prev => [...prev, { id: Date.now(), type: 'log', text: `[TOOL] Output: ${JSON.stringify(payload.data)}` }]);
          }
          else if (type === "final_response") {
            setIsProcessing(false);
            setChatHistory(prev => [...prev, { role: 'jarvis', text: payload.text }]);
          }
          else if (type === "user_message") {
            setChatHistory(prev => [...prev, { role: 'user', text: payload.text }]);
          }
          else if (type === "voice_status") {
            if (payload.status === "listening") {
              setIsListening(true);
              setFeed(prev => [...prev, { id: Date.now(), type: 'signal', text: '[VOICE] Mic active. Listening...' }]);
            } else if (payload.status === "processing") {
              setIsListening(false);
              setIsProcessing(true);
              setFeed(prev => [...prev, { id: Date.now(), type: 'log', text: '[VOICE] Processing audio...' }]);
            } else if (payload.status === "idle") {
              setIsListening(false);
              setIsProcessing(false);
              setFeed(prev => [...prev, { id: Date.now(), type: 'log', text: '[VOICE] Silence detected / Idle.' }]);
            }
          }
          else if (type === "audio_chunk") {
            const binaryString = window.atob(payload.audio_b64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const int16Array = new Int16Array(bytes.buffer);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }
            audioQueue.push({ buffer: float32Array, sampleRate: payload.sample_rate });
            if (!isPlaying) {
                if (audioCtx.state === 'suspended') audioCtx.resume();
                playNextAudio();
            }
          }
        } catch (e) {
          console.error("Error parsing WS message", e);
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        setIsProcessing(false);
        setFeed(prev => {
            const last = prev[prev.length - 1];
            if (last && last.text.includes('Waiting for Backend Kernel')) {
                return prev;
            }
            return [...prev, { id: Date.now(), type: 'log', text: '[SYSTEM] Waiting for Backend Kernel...' }];
        });
        reconnectTimer = setTimeout(connectWS, 3000); // Auto-reconnect every 3s
      };

      socket.onerror = (err) => {
        console.error("WebSocket error observed:", err);
        socket.close();
      };

      setWs(socket);
    };

    connectWS();

    return () => {
      clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, []);

  useEffect(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, feed, isProcessing, isConnected, isListening]);

  const handleSend = () => {
    if (!input.trim() || !ws) return;
    
    setChatHistory(prev => [...prev, { role: 'user', text: input }]);
    setIsProcessing(true);
    
    ws.send(JSON.stringify({
      type: "user_message",
      payload: { text: input }
    }));
    
    setInput("");
  };

  const handleMicClick = () => {
    if (!ws || !isConnected) return;
    stopAudio(); // Barge-in: Stop currently playing audio
    setIsListening(true);
    ws.send(JSON.stringify({ type: "start_voice_listening", payload: {} }));
  };

  return (
    <div className="dashboard-container">
      
      {/* LEFT PANEL - SYSTEM STATS */}
      <div className="panel">
        <div className="panel-header">System Diagnostics</div>
        
        <div className="system-stat">
          <div className="stat-label">Agent Core</div>
          <div className="stat-value">
            <span className={`status-ring ${!isConnected ? 'offline' : isProcessing ? 'active' : 'online'}`}></span> 
            {!isConnected ? 'OFFLINE' : isProcessing ? 'PROCESSING' : 'ONLINE'}
          </div>
        </div>

        <div className="system-stat">
          <div className="stat-label">Model Engine (Qwen)</div>
          <div className="stat-value">
            <span className={`status-ring ${!isConnected ? 'offline' : isProcessing ? 'active' : 'standby'}`}></span> 
            {!isConnected ? 'OFFLINE' : isProcessing ? 'COMPUTING' : 'STANDBY'}
          </div>
        </div>

        <div className="system-stat">
          <div className="stat-label">Memory Interface</div>
          <div className="stat-value">
            <span className={`status-ring ${isConnected ? 'online' : 'offline'}`}></span> 
            {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </div>
        </div>
        
        <div className="system-stat">
          <div className="stat-label">Active Context</div>
          <div className="stat-value" style={{ color: "var(--cyan-accent)", fontFamily: "'Consolas', monospace", fontSize: "14px", marginTop: "4px" }}>
            4,096 / 8,192
          </div>
        </div>
      </div>

      {/* CENTER PANEL - MAIN INTERACTION */}
      <div className="panel" style={{ background: "rgba(3, 5, 8, 0.8)" }}>
        <div className="panel-header" style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: "0", letterSpacing: "4px" }}>
          <div>Jarvis Interface</div>
          <canvas ref={canvasRef} width={250} height={40} style={{ marginTop: "15px", filter: "drop-shadow(0 0 5px var(--cyan-glow))" }} />
        </div>
        
        <div className="chat-window">
          <div style={{ flexGrow: 1 }}></div>
          {chatHistory.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.role}`}>
              {msg.text}
            </div>
          ))}
          {isProcessing && (
            <div className="chat-bubble jarvis thinking">
              ...
            </div>
          )}
          <div ref={endOfChatRef}></div>
        </div>

        <div className="command-bar-container">
          <button 
            className={`voice-btn ${isListening ? 'active pulsing' : ''}`} 
            title="Voice Input" 
            onClick={handleMicClick}
            disabled={!isConnected || isProcessing || isListening}
            style={isListening ? { color: "var(--cyan-accent)", textShadow: "0 0 10px var(--cyan-glow)" } : {}}
          >
            🎤
          </button>
          <input 
            type="text" 
            className="command-input" 
            placeholder={!isConnected ? "Connecting to Kernel..." : isListening ? "Listening... (speak now)" : "Awaiting command..."} 
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            autoFocus
            disabled={!isConnected || isProcessing || isListening}
          />
        </div>
      </div>

      {/* RIGHT PANEL - INTELLIGENCE FEED */}
      <div className="panel">
        <div className="panel-header">Intelligence Feed</div>
        
        <div className="feed-container">
          {feed.map(log => (
            <div key={log.id} className={`log-entry ${log.type}`}>
              {log.text}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}

export default App;
