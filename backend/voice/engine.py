import os
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import io
import queue
from backend.core.logger import logger

class VoiceEngine:
    def __init__(self, emitter=None):
        logger.info("  [Module] VoiceEngine initializing...")
        self.emitter = emitter
        
        self.SAMPLE_RATE = 16000
        self.MAX_RECORD = 30
        self.SILENCE_SECS = 1.5
        self.SILENCE_THRESH = 0.01
        self.KOKORO_VOICE = "bm_george"
        
        # We explicitly rely on the existing model files in Project J to prevent downloading 2GB again
        self.PROJECT_J_DIR = r"C:\Users\Dizzyeyes\Desktop\Project J"
        
        self._stt_reinit_attempts = 0
        self._tts_reinit_attempts = 0
        self._init_stt()
        self._init_tts()
            
        self._setup_mic()
        
        self.tts_queue = queue.Queue()
        import threading
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

    def _init_stt(self):
        if hasattr(self, 'asr') and self.asr is not None:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info("  [VoiceEngine] Initializing STT in CPU-only mode...")
            self.asr = WhisperModel("large-v3", device="cpu", compute_type="int8")
            logger.info("  [VoiceEngine] STT: faster-whisper large-v3 loaded safely on CPU.")
        except Exception as e:
            logger.error(f"  [VoiceEngine] STT initialization failed on first attempt: {e}")
            try:
                # Retry once on CPU
                logger.info("  [VoiceEngine] Retrying STT initialization on CPU...")
                self.asr = WhisperModel("large-v3", device="cpu", compute_type="int8")
                logger.info("  [VoiceEngine] STT: Retry successful.")
            except Exception as retry_err:
                logger.error(f"  [VoiceEngine] STT retry failed: {retry_err}. STT disabled.")
                self.asr = None

    def _init_tts(self):
        if hasattr(self, 'kokoro') and self.kokoro is not None:
            return
        try:
            from kokoro_onnx import Kokoro
            model_path = os.path.join(self.PROJECT_J_DIR, "kokoro-v0_19.onnx")
            voices_path = os.path.join(self.PROJECT_J_DIR, "voices.bin")
            self.kokoro = Kokoro(model_path, voices_path)
            logger.info("  [VoiceEngine] TTS: Kokoro loaded natively.")
        except Exception as e:
            logger.error(f"  [VoiceEngine] Failed to load TTS: {e}")
            self.kokoro = None
            
        self._setup_mic()
        
        self.tts_queue = queue.Queue()
        import threading
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

    def _tts_worker(self):
        while True:
            text = self.tts_queue.get()
            if text is None:
                break
            try:
                samples, sample_rate = self.kokoro.create(
                    text, voice=self.KOKORO_VOICE, speed=1.2, lang="en-us"
                )
                if self.emitter:
                    import base64
                    audio_int16 = (samples * 32767).astype(np.int16)
                    b64_data = base64.b64encode(audio_int16.tobytes()).decode('ascii')
                    self.emitter.emit("audio_chunk", {
                        "audio_b64": b64_data,
                        "sample_rate": sample_rate
                    })
            except Exception as e:
                logger.error(f"[VoiceEngine] TTS Worker Error: {e}")
            finally:
                self.tts_queue.task_done()

    def _setup_mic(self):
        self.mic_idx = None
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and ('Maono' in dev['name'] or 'OnePlus' in dev['name']):
                    self.mic_idx = i
                    break
            
            if self.mic_idx is None:
                self.mic_idx = sd.default.device[0] # Auto-pick default input
                
            if self.mic_idx is not None:
                device_name = devices[self.mic_idx]['name']
                logger.info(f"  [VoiceEngine] Microphone selected: [{self.mic_idx}] {device_name}")
            else:
                logger.warning("  [VoiceEngine] No working microphone found!")
        except Exception as e:
            logger.error(f"  [VoiceEngine] Failed to auto-select microphone: {e}")

    def normalize_audio(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        peak = float(np.max(np.abs(audio)))
        if peak < 0.001:
            return None
        gain = target_peak / peak
        return audio * gain

    def listen(self) -> dict:
        result = {"text": "", "error": None}
        if not hasattr(self, 'asr') or not self.asr:
            if getattr(self, '_stt_reinit_attempts', 0) < 1:
                logger.info("[VoiceEngine] STT is missing. Attempting runtime reinitialization...")
                self._stt_reinit_attempts = getattr(self, '_stt_reinit_attempts', 0) + 1
                self._init_stt()
            if not self.asr:
                logger.error("[VoiceEngine] STT reinitialization failed. Cannot listen.")
                result["error"] = "STT_FAILURE"
                return result
            
        logger.info("[VoiceEngine] Listening... (speak now)")
        if self.emitter:
            self.emitter.emit("voice_status", {"status": "listening"})
            
        q = queue.Queue()
        def callback(indata, frames, time_info, status):
            q.put(indata.copy())
            
        chunk_size = int(self.SAMPLE_RATE * 0.1)
        sil_chunks = int(self.SILENCE_SECS / 0.1)
        max_chunks = int(self.MAX_RECORD / 0.1)
        
        frames = []
        silent_cnt = 0
        speaking = False
        is_recording = False
        
        try:
            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=None, blocksize=chunk_size,
                                dtype="float32", device=self.mic_idx, callback=callback) as stream:
                for _ in range(max_chunks):
                    try:
                        block = q.get(timeout=2.0)
                    except queue.Empty:
                        break
                        
                    mono_block = np.mean(block, axis=1)
                    rms = float(np.sqrt(np.mean(mono_block ** 2)))
                    
                    if is_recording or rms > self.SILENCE_THRESH:
                        frames.append(mono_block)
                        if rms > self.SILENCE_THRESH:
                            if not is_recording:
                                is_recording = True
                            speaking = True
                            silent_cnt = 0
                        elif speaking:
                            silent_cnt += 1
                            if silent_cnt >= sil_chunks:
                                break
        except Exception as e:
            logger.error(f"[VoiceEngine] Mic stream failed: {e}")
            result["error"] = "MIC_FAILURE"
            return result
            
        if not speaking or not frames:
            if self.emitter:
                self.emitter.emit("voice_status", {"status": "idle"})
            return result
            
        raw_audio = np.concatenate(frames, axis=0)
        audio = self.normalize_audio(raw_audio)
        if audio is None:
            return result
            
        logger.info("[Voice] audio captured")
        
        if self.emitter:
            self.emitter.emit("voice_status", {"status": "processing"})
            
        logger.info("[Voice] transcribing")
        try:
            segments, _ = self.asr.transcribe(
                audio, language="en", beam_size=1,
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
            )
            text = " ".join(seg.text for seg in segments).strip()
            # Mandatory transcript validation
            if not text:
                return result
                
            # Relaxed hallucination filter
            lower_text = text.lower().strip()
            hallucinations = ["thank you.", "thanks.", "bye."]
            if lower_text in hallucinations and len(text) < 15:
                logger.warning(f"[VoiceEngine] Ignored probable hallucination: '{text}'")
                return result
            
            logger.info("[Voice] transcription complete")
            
            result["text"] = text
            return result
        except Exception as e:
            logger.error(f"[Voice] transcription failed safely: {e}")
            result["error"] = "STT_FAILURE"
            return result
            
    def speak(self, text: str):
        if not hasattr(self, 'kokoro') or not self.kokoro:
            if getattr(self, '_tts_reinit_attempts', 0) < 1:
                logger.info("[VoiceEngine] TTS is missing. Attempting runtime reinitialization...")
                self._tts_reinit_attempts = getattr(self, '_tts_reinit_attempts', 0) + 1
                self._init_tts()
            if not self.kokoro:
                logger.error("[VoiceEngine] TTS reinitialization failed. Cannot speak.")
                return ""
                
        if not text:
            return
            
        # Clean text
        text = text.replace("J.A.R.V.I.S.", "Jarvis").replace("J.A.R.V.I.S", "Jarvis")
        text = text.replace("*", "").replace("`", "").strip()
        if not text:
            return
            
        try:
            logger.info("[VoiceEngine] speaking output...")
            self.tts_queue.put(text)
        except Exception as e:
            logger.error(f"[VoiceEngine] Failed to queue TTS: {e}")
