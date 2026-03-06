// =====================================================================
// Vera Duplex Voice Interface v4
// Fixes: mic permission re-prompt, browser STT race, backend status timing
// =====================================================================

(() => {
'use strict';

const BASE_URL = 'http://llm.int:8888';

const VOICE_DEFAULTS = {
    sttMode:              'browser',
    ttsMode:              'browser',
    whisperEndpoint:      `${BASE_URL}/api/voice/transcribe`,
    remoteTtsEndpoint:    `${BASE_URL}/api/voice/synthesize`,
    whisperLanguage:      'en',
    whisperModel:         'base',
    remoteTtsVoice:       'default',
    remoteTtsFormat:      'wav',
    interruptOnSpeech:    true,
    autoSendAfterSilence: true,
    silenceMs:            1500,
    ttsRate:              1.0,
    audioGain:            1.0,
    noiseSuppression:     true,
    echoCancellation:     true,
};

// ─────────────────────────────────────────────────────────────────────────────
// DuplexVoiceController
// ─────────────────────────────────────────────────────────────────────────────

class DuplexVoiceController {
    constructor(veraChat) {
        this.vc = veraChat;
        this.cfg = this._loadCfg();

        // state
        this.sttActive   = false;
        this.ttsActive   = false;
        this.ttsSpeaking = false;
        this.interrupted = false;
        this.ttsQueue    = [];
        this.streamBuffer = '';
        this.spokenLen    = 0;

        // audio
        this.currentAudio     = null;
        this.currentUtterance = null;
        this.silenceTimer     = null;

        // Whisper recording — stream is kept alive between recordings
        this.mediaRecorder = null;
        this.audioChunks   = [];
        this.micStream     = null;   // held open — never released until explicit teardown
        this.audioCtx      = null;
        this.vadRunning    = false;

        // browser recognition — single instance, never recreated
        this.recognition      = null;
        this._recognitionBusy = false;  // true between start() and onend firing
        this._initRecognition();

        // TTS voices
        this.browserVoice = null;
        this._loadVoices();

        // backend — async, panel reads this.backend directly when opened
        this.backend = { stt: false, tts: false, checked: false };
        this._checkBackend();

        console.log('[Voice] Ready');
    }

    // ── config ──────────────────────────────────────────────────────────────

    _loadCfg() {
        try { return { ...VOICE_DEFAULTS, ...JSON.parse(localStorage.getItem('vera-voice-cfg') || '{}') }; }
        catch { return { ...VOICE_DEFAULTS }; }
    }

    saveCfg(patch) {
        Object.assign(this.cfg, patch);
        localStorage.setItem('vera-voice-cfg', JSON.stringify(this.cfg));
    }

    // ── backend status ───────────────────────────────────────────────────────

    async _checkBackend() {
        try {
            const r = await fetch(`${BASE_URL}/api/voice/status`, { signal: AbortSignal.timeout(4000) });
            const text = await r.text();
            console.log('[Voice] /api/voice/status raw:', r.status, text);
            if (r.ok) {
                let d;
                try { d = JSON.parse(text); } catch(e) { console.warn('[Voice] Bad JSON from status'); d = {}; }
                // Handle both possible field names
                this.backend.stt = !!(d.stt_available ?? d.stt ?? d.whisper_available ?? false);
                this.backend.tts = !!(d.tts_available ?? d.tts ?? false);
                this.backend.raw = d;
            } else {
                console.warn('[Voice] Status endpoint returned', r.status);
            }
        } catch(e) {
            console.warn('[Voice] Backend unreachable:', e.message);
        }
        this.backend.checked = true;
        this._updateUI();
    }

    // ── TTS voice loading ────────────────────────────────────────────────────

    _loadVoices() {
        if (!('speechSynthesis' in window)) return;
        const pick = () => {
            const vs = speechSynthesis.getVoices();
            if (!vs.length) return;
            this.browserVoice = vs.find(v => v.lang.startsWith('en-') && v.localService)
                             || vs.find(v => v.lang.startsWith('en'))
                             || vs[0] || null;
            console.log('[Voice] Browser voice:', this.browserVoice?.name);
        };
        speechSynthesis.onvoiceschanged = pick;
        pick(); // May already be loaded
    }

    // ── browser speech recognition (single persistent instance) ─────────────

    _initRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) { console.warn('[Voice] Web Speech API unavailable'); return; }

        const r = new SR();
        r.continuous      = true;
        r.interimResults  = true;
        r.lang            = 'en-US';
        this.recognition  = r;

        r.onstart = () => {
            this._recognitionBusy = true;
            console.log('[STT] Recognition started');
        };

        r.onresult = (e) => {
            let interim = '', final = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript;
                e.results[i].isFinal ? (final += t) : (interim += t);
            }
            const text = final || interim;
            const input = document.getElementById('messageInput');
            if (input && text) { input.value = text; input.dispatchEvent(new Event('input')); }
            if (text && this.cfg.interruptOnSpeech) this._interruptTTS();
            if (final && this.cfg.autoSendAfterSilence) this._armSilenceTimer(final);
            this._pulseVAD(!!text);
        };

        r.onend = () => {
            this._recognitionBusy = false;
            this._pulseVAD(false);
            // Snapshot sttActive NOW before the setTimeout fires
            // This prevents a race where stop() sets sttActive=false but
            // the delayed callback still sees the old value
            const shouldRestart = this.sttActive && this.cfg.sttMode === 'browser';
            console.log('[STT] onend, shouldRestart=', shouldRestart);
            if (shouldRestart) {
                setTimeout(() => {
                    // Re-check both flags — user may have stopped in the gap
                    if (this.sttActive && this.cfg.sttMode === 'browser' && !this._recognitionBusy) {
                        try { r.start(); }
                        catch(e) { console.log('[STT] Restart suppressed:', e.message); }
                    }
                }, 250);
            }
        };

        r.onerror = (e) => {
            if (e.error === 'no-speech' || e.error === 'aborted') return;
            console.warn('[STT] Error:', e.error);
            // On 'not-allowed' — mic permission denied
            if (e.error === 'not-allowed') {
                this.sttActive = false;
                this._updateUI();
                this.vc.setControlStatus?.('❌ Microphone permission denied');
            }
        };
    }

    // ── mic stream — acquire ONCE, hold open ────────────────────────────────

    async _acquireMic() {
        // Already have a live stream — reuse it
        if (this.micStream && this.micStream.active) {
            console.log('[Voice] Reusing existing mic stream');
            return true;
        }
        console.log('[Voice] Requesting mic permission...');
        try {
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    noiseSuppression: this.cfg.noiseSuppression,
                    echoCancellation: this.cfg.echoCancellation,
                    autoGainControl:  true,
                }
            });
            console.log('[Voice] Mic acquired');
            return true;
        } catch(e) {
            console.error('[Voice] Mic access failed:', e);
            this.vc.setControlStatus?.('❌ Microphone access denied');
            return false;
        }
    }

    _releaseMic() {
        if (this.micStream) {
            this.micStream.getTracks().forEach(t => t.stop());
            this.micStream = null;
            console.log('[Voice] Mic released');
        }
        this.vadRunning = false;
        if (this.audioCtx) {
            try { this.audioCtx.close(); } catch(e) {}
            this.audioCtx = null;
        }
    }

    // ── STT public API ───────────────────────────────────────────────────────

    async startSTT() {
        if (this.sttActive) return;

        if (this.cfg.sttMode === 'whisper' && this.backend.stt) {
            // Whisper mode needs mic
            if (!await this._acquireMic()) return;
        } else {
            // Browser mode — also warm up mic permission here so it doesn't
            // re-ask later if user switches to whisper mode. Silently.
            if (!this.micStream) {
                this._acquireMic().catch(() => {}); // fire and forget — don't block
            }
        }

        this.sttActive = true;
        this._updateUI();

        if (this.cfg.sttMode === 'whisper' && this.backend.stt) {
            this._startWhisperRecording();
        } else {
            if (!this.recognition) {
                alert('Web Speech API not available in this browser.');
                this.sttActive = false;
                this._updateUI();
                return;
            }
            if (!this._recognitionBusy) {
                try { this.recognition.start(); }
                catch(e) { console.warn('[STT] Start error:', e.message); }
            }
        }

        this.vc.setControlStatus?.('🎤 Listening...', 0);
    }

    stopSTT(send = false) {
        if (!this.sttActive) return;
        this.sttActive = false;  // set BEFORE calling stop() so onend doesn't restart
        clearTimeout(this.silenceTimer);
        this._pulseVAD(false);

        if (this.cfg.sttMode === 'whisper' && this.backend.stt) {
            this._stopWhisperRecording(send);
            // Don't release mic here — keep it warm to avoid re-prompt
        } else {
            if (this._recognitionBusy) {
                try { this.recognition.stop(); }
                catch(e) { console.log('[STT] Stop error:', e.message); }
            }
        }

        this._updateUI();
        this.vc.setControlStatus?.('', 100);
    }

    toggleSTT() { this.sttActive ? this.stopSTT(false) : this.startSTT(); }

    // ── Whisper recording ────────────────────────────────────────────────────

    _startWhisperRecording() {
        if (!this.micStream?.active) { console.warn('[STT] No mic stream'); return; }
        this.audioChunks = [];
        this.mediaRecorder = new MediaRecorder(this.micStream);
        this.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) this.audioChunks.push(e.data); };
        this.mediaRecorder.start(100);
        this._startVAD();
        console.log('[STT] Whisper recording started');
    }

    _stopWhisperRecording(autoSend = true) {
        if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') return;
        this.vadRunning = false;

        this.mediaRecorder.onstop = async () => {
            const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
            this.audioChunks = [];
            if (blob.size < 500) { console.log('[STT] Audio too short, skipping'); return; }
            const text = await this._whisperTranscribe(blob);
            if (text) {
                const input = document.getElementById('messageInput');
                if (input) { input.value = text; input.dispatchEvent(new Event('input')); }
                if (autoSend) setTimeout(() => this.vc.sendMessage?.(), 200);
            }
        };

        try { this.mediaRecorder.stop(); } catch(e) {}
    }

    async _whisperTranscribe(blob) {
        this.vc.setControlStatus?.('🧠 Transcribing...', 0);
        const fd = new FormData();
        fd.append('audio', blob, 'recording.webm');
        fd.append('language', this.cfg.whisperLanguage);
        fd.append('model', this.cfg.whisperModel);
        if (this.vc.sessionId) fd.append('session_id', this.vc.sessionId);
        try {
            const r = await fetch(this.cfg.whisperEndpoint, { method: 'POST', body: fd });
            if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
            const d = await r.json();
            const text = (d.text || d.transcription || '').trim();
            this.vc.setControlStatus?.(text ? `✅ "${text.slice(0, 50)}"` : '⚠️ No speech detected', 3000);
            return text || null;
        } catch(e) {
            console.error('[STT] Whisper error:', e);
            this.vc.setControlStatus?.(`❌ Transcription failed: ${e.message}`);
            return null;
        }
    }

    _startVAD() {
        if (this.vadRunning || !this.micStream) return;
        this.vadRunning = true;
        try {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const src      = this.audioCtx.createMediaStreamSource(this.micStream);
            const analyser = this.audioCtx.createAnalyser();
            analyser.fftSize = 512;
            src.connect(analyser);
            const buf = new Uint8Array(analyser.frequencyBinCount);
            let silentFrames = 0;
            const check = () => {
                if (!this.vadRunning) return;
                analyser.getByteFrequencyData(buf);
                const vol = buf.reduce((a, b) => a + b, 0) / buf.length;
                const speaking = vol > 12;
                this._pulseVAD(speaking);
                if (speaking) {
                    silentFrames = 0;
                    if (this.cfg.interruptOnSpeech) this._interruptTTS();
                } else {
                    if (++silentFrames > 45 && this.cfg.autoSendAfterSilence && this.sttActive) {
                        this.stopSTT(true); return;
                    }
                }
                requestAnimationFrame(check);
            };
            requestAnimationFrame(check);
        } catch(e) { console.warn('[VAD] failed:', e); }
    }

    _armSilenceTimer(text) {
        clearTimeout(this.silenceTimer);
        if (!text.trim()) return;
        this.silenceTimer = setTimeout(() => {
            if (this.sttActive && this.cfg.autoSendAfterSilence) {
                this.stopSTT(false);
                setTimeout(() => this.vc.sendMessage?.(), 100);
            }
        }, this.cfg.silenceMs);
    }

    // ── TTS public API ───────────────────────────────────────────────────────

    enableTTS()  { this.ttsActive = true;  this._updateUI(); }
    disableTTS() { this._interruptTTS(); this.ttsActive = false; this._updateUI(); }
    toggleTTS()  { this.ttsActive ? this.disableTTS() : this.enableTTS(); }

    onStreamChunk(fullText) {
        if (!this.ttsActive) return;
        const newText = fullText.slice(this.spokenLen);
        if (!newText) return;
        this.streamBuffer += newText;
        this.spokenLen = fullText.length;
        this._flushBuffer(false);
    }

    onStreamEnd(fullText) {
        if (!this.ttsActive) return;
        const remaining = fullText.slice(this.spokenLen);
        if (remaining.trim()) this.streamBuffer += remaining;
        this.spokenLen = 0;
        this._flushBuffer(true);
    }

    speakFull(text) {
        if (!this.ttsActive || !text.trim()) return;
        const cleaned = this._clean(text);
        const sentences = cleaned.match(/[^.!?…]+[.!?…]?\s*/g) || [cleaned];
        sentences.forEach(s => { if (s.trim()) this.ttsQueue.push(s.trim()); });
        this._drain();
    }

    stopSpeaking() { this._interruptTTS(); }

    // ── TTS internals ────────────────────────────────────────────────────────

    _interruptTTS() {
        this.interrupted = true;
        this.ttsQueue    = [];
        this.streamBuffer = '';
        this.ttsSpeaking = false;
        if ('speechSynthesis' in window) speechSynthesis.cancel();
        if (this.currentAudio) {
            try { this.currentAudio.pause(); this.currentAudio.src = ''; } catch(e) {}
            this.currentAudio = null;
        }
        this._updateUI();
    }

    _flushBuffer(flushAll) {
        if (!this.streamBuffer.trim()) return;
        let speak = '', rest = '';
        if (flushAll) {
            speak = this.streamBuffer;
        } else {
            const m = [...this.streamBuffer.matchAll(/[.!?…]\s/g)];
            if (!m.length) {
                if (this.streamBuffer.length < 80) return;
                const wb = this.streamBuffer.lastIndexOf(' ');
                if (wb < 20) return;
                speak = this.streamBuffer.slice(0, wb);
                rest  = this.streamBuffer.slice(wb + 1);
            } else {
                const last = m[m.length - 1];
                speak = this.streamBuffer.slice(0, last.index + last[0].length);
                rest  = this.streamBuffer.slice(last.index + last[0].length);
            }
        }
        this.streamBuffer = rest;
        const cleaned = this._clean(speak);
        if (cleaned) { this.ttsQueue.push(cleaned); this._drain(); }
    }

    async _drain() {
        if (this.ttsSpeaking || !this.ttsQueue.length) return;
        this.ttsSpeaking = true;
        this.interrupted = false;
        while (this.ttsQueue.length && !this.interrupted) {
            await this._speakSegment(this.ttsQueue.shift());
        }
        this.ttsSpeaking = false;
        this._updateUI();
    }

    async _speakSegment(text) {
        if (!text || this.interrupted) return;
        if (this.cfg.ttsMode === 'remote' && this.backend.tts) {
            await this._speakRemote(text);
        } else {
            await this._speakBrowser(text);
        }
    }

    _speakBrowser(text) {
        return new Promise(resolve => {
            if (this.interrupted || !text.trim()) { resolve(); return; }
            if (!('speechSynthesis' in window)) { resolve(); return; }

            speechSynthesis.cancel();

            const go = () => {
                if (this.interrupted) { resolve(); return; }
                const utt  = new SpeechSynthesisUtterance(text.trim());
                const vs   = speechSynthesis.getVoices();
                utt.voice  = vs.find(v => v.lang.startsWith('en') && v.localService)
                          || vs.find(v => v.lang.startsWith('en'))
                          || null;
                utt.rate   = parseFloat(localStorage.getItem('vera-tts-rate') || String(this.cfg.ttsRate));
                utt.volume = this.cfg.audioGain;
                utt.pitch  = 1.0;
                this.currentUtterance = utt;
                utt.onend   = () => { this.currentUtterance = null; resolve(); };
                utt.onerror = (e) => { console.warn('[TTS] Browser error:', e.error); this.currentUtterance = null; resolve(); };
                speechSynthesis.speak(utt);
                // Chrome workaround: first utterance is sometimes silently dropped
                setTimeout(() => {
                    if (!speechSynthesis.speaking && !speechSynthesis.pending && !this.interrupted) {
                        speechSynthesis.speak(utt);
                    }
                }, 300);
            };

            const vs = speechSynthesis.getVoices();
            if (vs.length) go();
            else { speechSynthesis.onvoiceschanged = () => { speechSynthesis.onvoiceschanged = null; go(); }; setTimeout(go, 500); }
        });
    }

    async _speakRemote(text) {
        try {
            const r = await fetch(this.cfg.remoteTtsEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, voice: this.cfg.remoteTtsVoice, format: this.cfg.remoteTtsFormat, session_id: this.vc.sessionId || null })
            });
            if (!r.ok) throw new Error(`${r.status}`);
            const blob = await r.blob();
            if (!blob.size) throw new Error('empty audio');
            const url = URL.createObjectURL(blob);
            await this._playUrl(url);
            URL.revokeObjectURL(url);
        } catch(e) {
            console.error('[TTS] Remote failed, using browser:', e.message);
            await this._speakBrowser(text);
        }
    }

    _playUrl(url) {
        return new Promise(resolve => {
            if (this.interrupted) { resolve(); return; }
            const a  = new Audio(url);
            a.volume = this.cfg.audioGain;
            this.currentAudio = a;
            a.onended = () => { this.currentAudio = null; resolve(); };
            a.onerror = () => { this.currentAudio = null; resolve(); };
            a.play().catch(() => resolve());
        });
    }

    _clean(text) {
        return text
            .replace(/```[\s\S]*?```/g, ' code block. ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/#{1,6} /g, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/<[^>]+>/g, '')
            .replace(/\n+/g, ' ')
            .trim();
    }

    _pulseVAD(active) {
        document.getElementById('vera-vad-indicator')?.classList.toggle('speaking', active);
        document.getElementById('vera-stt-btn')?.classList.toggle('vad-active', active);
    }

    _updateUI() {
        document.getElementById('vera-stt-btn')?.classList.toggle('active', this.sttActive);
        document.getElementById('vera-tts-btn')?.classList.toggle('active', this.ttsActive);
        // keep legacy control bar buttons in sync
        document.getElementById('toggle-tts')?.classList.toggle('active', this.ttsActive);
        document.getElementById('toggle-stt')?.classList.toggle('active', this.sttActive);

        const status = document.getElementById('vera-voice-status');
        if (status) {
            if (this.sttActive && this.ttsActive)      status.textContent = '🔄 Duplex';
            else if (this.sttActive)                   status.textContent = '🎤 Listening';
            else if (this.ttsActive && this.ttsSpeaking) status.textContent = '🔊 Speaking';
            else if (this.ttsActive)                   status.textContent = '🔊 Armed';
            else                                       status.textContent = '';
        }
    }

    // called when the module is being replaced / page unloads
    destroy() {
        this.stopSTT(false);
        this._interruptTTS();
        this._releaseMic();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Patch VeraChat
// ─────────────────────────────────────────────────────────────────────────────

const _origInitModern = VeraChat.prototype.initModernFeatures;

VeraChat.prototype.initModernFeatures = function() {
    if (_origInitModern) _origInitModern.call(this);

    // Tear down original recognition so it doesn't fight ours
    // Only do this ONCE — if we've already installed our controller, leave it alone
    if (this._voice) {
        // Already installed — just make sure the bar is present
        setTimeout(() => this._addVoiceBar(), 150);
        return;
    }

    if (this.recognition) {
        try { this.recognition.abort(); } catch(e) {}
        this.recognition = null;
    }
    if ('speechSynthesis' in window) speechSynthesis.cancel();

    this._voice = new DuplexVoiceController(this);
    setTimeout(() => this._addVoiceBar(), 150);
    console.log('[Voice] Module installed');
};

VeraChat.prototype.toggleTTS = function() {
    this._voice?.toggleTTS();
    this.ttsEnabled = this._voice?.ttsActive || false;
};

VeraChat.prototype.toggleSTT = function() {
    this._voice?.toggleSTT();
    this.sttActive = this._voice?.sttActive || false;
};

VeraChat.prototype.speakStreamingText = function(fullText) {
    this._voice?.onStreamChunk(fullText);
};

VeraChat.prototype.finalizeTTS = function(fullText) {
    this._voice?.onStreamEnd(fullText);
};

VeraChat.prototype.speakText = function(text) {
    this._voice?.speakFull(text);
};

VeraChat.prototype.openVoiceSettings = function() {
    if (this._voice) _openSettings(this._voice);
};

// ─────────────────────────────────────────────────────────────────────────────
// Voice bar
// ─────────────────────────────────────────────────────────────────────────────

VeraChat.prototype._addVoiceBar = function() {
    if (document.getElementById('vera-voice-bar')) return;
    const self = this;

    const bar = document.createElement('div');
    bar.id = 'vera-voice-bar';
    bar.innerHTML = `
        <button id="vera-stt-btn" class="vvb-btn" title="Voice input (STT)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
            STT
        </button>
        <div id="vera-vad-indicator" class="vera-vad">
            <span class="vad-bar"></span><span class="vad-bar"></span>
            <span class="vad-bar"></span><span class="vad-bar"></span>
            <span class="vad-bar"></span>
        </div>
        <span id="vera-voice-status" class="vvb-status"></span>
        <div style="flex:1"></div>
        <button id="vera-tts-btn" class="vvb-btn" title="Voice output (TTS)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M11 5L6 9H2v6h4l5 4V5z"/>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
            </svg>
            TTS
        </button>
        <button id="vera-stop-btn" class="vvb-btn vvb-stop" title="Stop speaking">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                <rect x="5" y="5" width="14" height="14" rx="2"/>
            </svg>
            Stop
        </button>
        <button id="vera-voice-cfg-btn" class="vvb-btn vvb-cfg" title="Voice settings">⚙</button>
    `;

    bar.querySelector('#vera-stt-btn').addEventListener('click',     e => { e.stopPropagation(); self.toggleSTT(); });
    bar.querySelector('#vera-tts-btn').addEventListener('click',     e => { e.stopPropagation(); self.toggleTTS(); });
    bar.querySelector('#vera-stop-btn').addEventListener('click',    e => { e.stopPropagation(); self._voice?.stopSpeaking(); });
    bar.querySelector('#vera-voice-cfg-btn').addEventListener('click', e => { e.stopPropagation(); self.openVoiceSettings(); });

    const controlBar = document.getElementById('chat-control-bar');
    const msgInput   = document.getElementById('messageInput');

    if (controlBar) {
        controlBar.insertAdjacentElement('afterend', bar);
        console.log('[Voice] Bar → after #chat-control-bar');
    } else if (msgInput) {
        let container = msgInput.parentElement;
        while (container.parentElement && container.parentElement.id !== 'tab-chat') {
            container = container.parentElement;
        }
        container.insertAdjacentElement('beforebegin', bar);
        console.log('[Voice] Bar → before input container');
    } else {
        document.getElementById('tab-chat')?.appendChild(bar);
        console.log('[Voice] Bar → appended to #tab-chat');
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// Settings panel — reads live backend state when opened
// ─────────────────────────────────────────────────────────────────────────────

async function _openSettings(ctrl) {
    document.getElementById('vera-voice-panel')?.remove();

    // If backend hasn't been checked yet, wait for it (max 2s)
    if (!ctrl.backend.checked) {
        const started = Date.now();
        await new Promise(resolve => {
            const poll = setInterval(() => {
                if (ctrl.backend.checked || Date.now() - started > 2000) {
                    clearInterval(poll); resolve();
                }
            }, 100);
        });
    }

    const c  = ctrl.cfg;
    const bs = ctrl.backend;

    const sttStatus = bs.stt ? '✅ Whisper available' : '❌ not available';
    const ttsStatus = bs.tts ? '✅ available'         : '❌ not available';
    const rawStr = bs.raw ? JSON.stringify(bs.raw).slice(0, 120) : 'no response yet';

    const p = document.createElement('div');
    p.id = 'vera-voice-panel';
    p.innerHTML = `
        <div class="vvp-backdrop"></div>
        <div class="vvp-box">
            <div class="vvp-head">
                <span>🎙️ Voice Settings</span>
                <button id="vvp-close">✕</button>
            </div>
            <div class="vvp-body">

                <div class="vvp-status-row">
                    <span>Backend STT: <b class="${bs.stt?'ok':'na'}">${sttStatus}</b></span>
                    <span>Backend TTS: <b class="${bs.tts?'ok':'na'}">${ttsStatus}</b></span>
                    <button id="vvp-recheck" class="vvp-recheck-btn" title="Re-check backend">↻ Recheck</button>
                    <span class="vvp-raw" title="${rawStr}">${rawStr}</span>
                </div>

                <div class="vvp-section">🎤 Speech Input (STT)</div>

                <label class="vvp-row">Engine
                    <select id="vvp-stt-mode">
                        <option value="browser" ${c.sttMode==='browser'?'selected':''}>Browser (Web Speech API)</option>
                        <option value="whisper" ${c.sttMode==='whisper'?'selected':''}>Whisper (via backend)</option>
                    </select>
                </label>
                <div id="vvp-whisper-rows" style="display:${c.sttMode==='whisper'?'contents':'none'}">
                    <label class="vvp-row">Endpoint
                        <input type="text" id="vvp-whisper-ep" value="${c.whisperEndpoint}">
                    </label>
                    <label class="vvp-row">Model
                        <select id="vvp-whisper-model">
                            ${['tiny','base','small','medium','large'].map(m =>
                                `<option value="${m}" ${c.whisperModel===m?'selected':''}>${m}</option>`
                            ).join('')}
                        </select>
                    </label>
                    <label class="vvp-row">Language
                        <input type="text" id="vvp-whisper-lang" value="${c.whisperLanguage}" style="max-width:60px">
                    </label>
                </div>
                <label class="vvp-row">Auto-send after silence
                    <input type="checkbox" id="vvp-auto-send" ${c.autoSendAfterSilence?'checked':''}>
                </label>
                <label class="vvp-row">Silence timeout (ms)
                    <input type="number" id="vvp-silence-ms" value="${c.silenceMs}" min="300" max="5000" step="100" style="max-width:80px">
                </label>
                <label class="vvp-row">Interrupt TTS when I speak
                    <input type="checkbox" id="vvp-interrupt" ${c.interruptOnSpeech?'checked':''}>
                </label>

                <div class="vvp-section">🔊 Voice Output (TTS)</div>

                <label class="vvp-row">Engine
                    <select id="vvp-tts-mode">
                        <option value="browser" ${c.ttsMode==='browser'?'selected':''}>Browser (Web Speech)</option>
                        <option value="remote"  ${c.ttsMode==='remote' ?'selected':''}>Remote endpoint</option>
                    </select>
                </label>
                <div id="vvp-remote-rows" style="display:${c.ttsMode==='remote'?'contents':'none'}">
                    <label class="vvp-row">TTS Endpoint
                        <input type="text" id="vvp-remote-ep" value="${c.remoteTtsEndpoint}">
                    </label>
                    <label class="vvp-row">Voice
                        <input type="text" id="vvp-remote-voice" value="${c.remoteTtsVoice}" style="max-width:120px">
                    </label>
                    <label class="vvp-row">Format
                        <select id="vvp-remote-fmt">
                            ${['wav','mp3','ogg'].map(f =>
                                `<option value="${f}" ${c.remoteTtsFormat===f?'selected':''}>${f.toUpperCase()}</option>`
                            ).join('')}
                        </select>
                    </label>
                </div>
                <label class="vvp-row">Speech rate
                    <div class="vvp-slider-row">
                        <input type="range" id="vvp-rate" min="0.5" max="2" step="0.05" value="${c.ttsRate}">
                        <span id="vvp-rate-val">${Number(c.ttsRate).toFixed(2)}×</span>
                    </div>
                </label>
                <label class="vvp-row">Volume
                    <div class="vvp-slider-row">
                        <input type="range" id="vvp-vol" min="0" max="1" step="0.05" value="${c.audioGain}">
                        <span id="vvp-vol-val">${Math.round(c.audioGain*100)}%</span>
                    </div>
                </label>
                <label class="vvp-row">Noise suppression
                    <input type="checkbox" id="vvp-noise" ${c.noiseSuppression?'checked':''}>
                </label>

                <div class="vvp-actions">
                    <button id="vvp-test">🔊 Test TTS</button>
                    <button id="vvp-save" class="vvp-primary">Save</button>
                </div>

            </div>
        </div>
    `;

    document.body.appendChild(p);
    requestAnimationFrame(() => p.classList.add('open'));

    const q = id => document.getElementById(id);

    const close = () => { p.classList.remove('open'); setTimeout(() => p.remove(), 200); };
    q('vvp-close').onclick = close;
    p.querySelector('.vvp-backdrop').onclick = close;

    q('vvp-stt-mode').onchange = e => {
        q('vvp-whisper-rows').style.display = e.target.value === 'whisper' ? 'contents' : 'none';
    };
    q('vvp-tts-mode').onchange = e => {
        q('vvp-remote-rows').style.display = e.target.value === 'remote' ? 'contents' : 'none';
    };
    q('vvp-rate').oninput = e => q('vvp-rate-val').textContent = Number(e.target.value).toFixed(2) + '×';
    q('vvp-vol').oninput  = e => q('vvp-vol-val').textContent  = Math.round(e.target.value * 100) + '%';

    q('vvp-recheck').onclick = async () => {
        q('vvp-recheck').textContent = '…';
        ctrl.backend.checked = false;
        await ctrl._checkBackend();
        close();
        _openSettings(ctrl);
    };

    q('vvp-test').onclick = () => {
        ctrl.ttsActive = true;
        ctrl._updateUI();
        ctrl._speakBrowser('Vera voice output is working correctly.');
    };

    q('vvp-save').onclick = () => {
        const rate = parseFloat(q('vvp-rate').value);
        localStorage.setItem('vera-tts-rate', String(rate));
        ctrl.saveCfg({
            sttMode:              q('vvp-stt-mode').value,
            whisperEndpoint:      q('vvp-whisper-ep')?.value    || c.whisperEndpoint,
            whisperModel:         q('vvp-whisper-model')?.value || c.whisperModel,
            whisperLanguage:      q('vvp-whisper-lang')?.value  || c.whisperLanguage,
            ttsMode:              q('vvp-tts-mode').value,
            remoteTtsEndpoint:    q('vvp-remote-ep')?.value     || c.remoteTtsEndpoint,
            remoteTtsVoice:       q('vvp-remote-voice')?.value  || c.remoteTtsVoice,
            remoteTtsFormat:      q('vvp-remote-fmt')?.value    || c.remoteTtsFormat,
            ttsRate:              rate,
            audioGain:            parseFloat(q('vvp-vol').value),
            autoSendAfterSilence: q('vvp-auto-send').checked,
            silenceMs:            parseInt(q('vvp-silence-ms').value),
            interruptOnSpeech:    q('vvp-interrupt').checked,
            noiseSuppression:     q('vvp-noise').checked,
        });
        close();
        ctrl.vc.setControlStatus?.('✅ Voice settings saved', 2000);
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// CSS
// ─────────────────────────────────────────────────────────────────────────────

const css = `
#vera-voice-bar {
    display: flex !important;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: var(--panel-bg, #1e293b);
    border-bottom: 1px solid var(--border, #334155);
    min-height: 34px;
    flex-shrink: 0;
    width: 100%;
    box-sizing: border-box;
    overflow: visible !important;
}
.vvb-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 9px;
    background: transparent;
    border: 1px solid var(--border, #334155);
    border-radius: 5px;
    color: var(--text-muted, #94a3b8);
    cursor: pointer; font-size: 11px; font-weight: 500;
    transition: all 0.15s; white-space: nowrap; user-select: none;
}
.vvb-btn:hover { background: var(--bg,#0f172a); color: var(--text,#e2e8f0); border-color: var(--accent,#3b82f6); }
.vvb-btn.active { background: var(--accent,#3b82f6); border-color: var(--accent,#3b82f6); color: #fff; }
.vvb-btn.vad-active { box-shadow: 0 0 0 2px rgba(59,130,246,.4); }
.vvb-stop { color: #ef4444; border-color: rgba(239,68,68,.4); }
.vvb-stop:hover { background: rgba(239,68,68,.1); border-color: #ef4444; }
.vvb-cfg { padding: 3px 8px; font-size: 14px; }
.vvb-status { font-size: 11px; color: var(--accent,#3b82f6); font-weight: 500; min-width: 60px; }

.vera-vad { display: flex; align-items: center; gap: 2px; height: 18px; opacity: .3; transition: opacity .2s; }
.vera-vad.speaking { opacity: 1; }
.vad-bar { display: block; width: 3px; height: 4px; background: var(--accent,#3b82f6); border-radius: 2px; }
.vera-vad.speaking .vad-bar { animation: vadS .35s ease-in-out infinite alternate; }
.vad-bar:nth-child(1){animation-delay:0s}
.vad-bar:nth-child(2){animation-delay:.07s}
.vad-bar:nth-child(3){animation-delay:.14s}
.vad-bar:nth-child(4){animation-delay:.07s}
.vad-bar:nth-child(5){animation-delay:0s}
@keyframes vadS { from{height:3px} to{height:16px} }

/* Settings panel */
#vera-voice-panel {
    position: fixed; inset: 0; z-index: 300000;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; transition: opacity .18s; pointer-events: none;
}
#vera-voice-panel.open { opacity: 1; pointer-events: all; }
.vvp-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,.55); backdrop-filter: blur(3px); }
.vvp-box {
    position: relative; width: min(460px,95vw); max-height: 90vh;
    background: var(--panel-bg,#1e293b); border: 1px solid var(--border,#334155);
    border-radius: 10px; box-shadow: 0 20px 50px rgba(0,0,0,.5);
    display: flex; flex-direction: column; overflow: hidden;
    transform: translateY(-8px); transition: transform .18s;
}
#vera-voice-panel.open .vvp-box { transform: translateY(0); }
.vvp-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; font-size: 14px; font-weight: 600; color: var(--text,#e2e8f0);
    border-bottom: 1px solid var(--border,#334155); background: var(--bg,#0f172a); flex-shrink:0;
}
.vvp-head button { background:none; border:none; color:var(--text-muted,#94a3b8); cursor:pointer; font-size:18px; padding:2px 5px; border-radius:3px; }
.vvp-head button:hover { color:var(--text,#e2e8f0); }
.vvp-body { padding:14px; overflow-y:auto; display:flex; flex-direction:column; gap:6px; }
.vvp-status-row {
    display:flex; align-items:center; gap:10px; flex-wrap:wrap;
    font-size:11px; color:var(--text-muted,#94a3b8);
    padding:7px 10px; background:var(--bg,#0f172a); border-radius:6px;
}
.vvp-status-row b.ok  { color: #4ade80; }
.vvp-status-row b.na  { color: #f87171; }
.vvp-recheck-btn {
    margin-left:auto; background:transparent; border:1px solid var(--border,#334155);
    color:var(--text-muted,#94a3b8); cursor:pointer; border-radius:4px;
    padding:2px 7px; font-size:13px;
}
.vvp-recheck-btn:hover { border-color:var(--accent,#3b82f6); color:var(--text,#e2e8f0); }
.vvp-raw { font-size:10px; color:var(--text-muted,#64748b); font-family:monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:200px; }
.vvp-section { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:var(--accent,#3b82f6); margin-top:4px; }
.vvp-row {
    display:flex; align-items:center; justify-content:space-between; gap:10px;
    font-size:12px; color:var(--text,#e2e8f0);
    padding:6px 0; border-bottom:1px solid rgba(51,65,85,.5);
}
.vvp-row input[type=text], .vvp-row input[type=number], .vvp-row select {
    background:var(--bg,#0f172a); border:1px solid var(--border,#334155);
    border-radius:4px; color:var(--text,#e2e8f0); padding:4px 8px;
    font-size:12px; flex:1; min-width:0; max-width:240px;
}
.vvp-row input[type=checkbox] { width:15px; height:15px; cursor:pointer; }
.vvp-slider-row { display:flex; align-items:center; gap:8px; }
.vvp-slider-row input[type=range] { width:100px; }
.vvp-slider-row span { font-size:11px; color:var(--text-muted,#94a3b8); min-width:34px; }
.vvp-actions { display:flex; justify-content:flex-end; gap:8px; padding-top:8px; }
.vvp-actions button {
    padding:7px 14px; border-radius:5px; font-size:12px; cursor:pointer;
    background:transparent; border:1px solid var(--border,#334155);
    color:var(--text-muted,#94a3b8); transition:all .15s;
}
.vvp-actions button:hover { border-color:var(--accent,#3b82f6); color:var(--text,#e2e8f0); }
.vvp-primary { background:var(--accent,#3b82f6) !important; border-color:var(--accent,#3b82f6) !important; color:#fff !important; font-weight:600 !important; }
.vvp-primary:hover { background:var(--accent-hover,#2563eb) !important; }
`;

if (!document.getElementById('vera-voice-css')) {
    const s = document.createElement('style');
    s.id = 'vera-voice-css';
    s.textContent = css;
    document.head.appendChild(s);
}

console.log('[Voice] Module parsed');
})();