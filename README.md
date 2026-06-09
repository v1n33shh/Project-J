# Jarvis OS - Real-Time AI Desktop Assistant

Jarvis OS is a modular, real-time, dual-streaming AI operating system designed for your desktop. It features a continuous live voice pipeline (with automatic CPU fallback), real-time WebSocket communication, and an animated React visualizer UI.

## Features
- **Real-time Dual-Streaming Architecture:** Streams both AI speech and transcriptions directly to the UI without blocking.
- **Robust Voice Pipeline:** Employs `faster-whisper` for STT and `kokoro-onnx` for TTS with intelligent watchdog limits and hardware-fault recovery.
- **Agentic Loop Integration:** Memory storage, dynamic tool usage, and Qwen LLM decision-making underneath.

---

## Installation & Setup (For Developers)

To run this locally, you need Python and Node.js installed.

### 1. Clone the Repository
```bash
git clone https://github.com/v1n33shh/Project-J.git
cd Project-J
```

### 2. Backend Setup (Python)
You need to install the dependencies for the Python engine. We highly recommend using a virtual environment (`.venv`).

```bash
# Create a virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Install all required pip packages
pip install -r requirements.txt
```

> **Note on Voice Models:** The voice engine expects `kokoro-v0_19.onnx` and `voices.bin` to exist locally. You may need to download these weights if they aren't included in the repo.

### 3. Frontend Setup (React/Node)
Open a new terminal window to set up the UI dashboard.

```bash
cd ui
npm install
```

---

## Running the App

The easiest way to run the application is to double-click the `run_debug.bat` file located in the root folder. 

Alternatively, to run it manually across two terminals:

**Terminal 1 (Backend):**
```bash
# Ensure .venv is activated
python run.py
```

**Terminal 2 (Frontend):**
```bash
cd ui
npm run dev
```

---

## Contributing
Contributions, issues, and feature requests are welcome! If you want to add new Tools to the agent or improve the Voice pipeline, feel free to submit a Pull Request.

## License
This project is legally protected under the **GNU General Public License v3.0**. 
See the `LICENSE` file for details.
