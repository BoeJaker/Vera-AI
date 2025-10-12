def stop_tts():
    """Stop any currently playing TTS and clear the queue"""
    js_code = """
    <script>
    console.log('Attempting to stop TTS...');
    
    function tryStop() {
        const contexts = [window, window.parent, window.top];
        
        for (let i = 0; i < contexts.length; i++) {
            try {
                const ctx = contexts[i];
                if (ctx && ctx.stopTTS && typeof ctx.stopTTS === 'function') {
                    console.log('Found stopTTS in context ' + i + ', calling...');
                    ctx.stopTTS();
                    return true;
                }
            } catch (e) {
                console.log('Context ' + i + ' stopTTS failed:', e.message);
            }
        }
        
        console.error('stopTTS function not found in any context!');
        return false;
    }
    
    tryStop();
    </script>
    """
    components.html(js_code, height=0)

def clear_tts_queue():
    """Clear the TTS queue without stopping current playback"""
    js_code = """
    <script>
    console.log('Attempting to clear TTS queue...');
    
    function tryClear() {
        const contexts = [window, window.parent, window.top];
        
        for (let i = 0; i < contexts.length; i++) {
            try {
                const ctx = contexts[i];
                if (ctx && ctx.clearTTSQueue && typeof ctx.clearTTSQueue === 'function') {
                    console.log('Found clearTTSQueue in context ' + i + ', calling...');
                    ctx.clearTTSQueue();
                    return true;
                }
            } catch (e) {
                console.log('Context ' + i + ' clearTTSQueue failed:', e.message);
            }
        }
        
        console.error('clearTTSQueue function not found in any context!');
        return false;
    }
    
    tryClear();
    </script>
    """
    components.html(js_code, height=0)# app.py
    
import streamlit as st
import streamlit.components.v1 as components
import time
import json
import re
import os
import io
import base64
from typing import List, Dict, Any
from urllib.parse import urlparse
from conversation_memory_graph import ConversationGraphPanel

# Optional TTS dependency
try:
    from gtts import gTTS
    GTTs_AVAILABLE = True
except Exception:
    GTTs_AVAILABLE = False

# Import Vera - adjust path/import if needed
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from vera import Vera

# --------------------------
# Enhanced TTS Component
# --------------------------

@st.cache_resource
def get_tts_component_html():
    """Get the persistent TTS component HTML that registers functions globally"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            #tts-container {
                padding: 10px;
                background: #f0f2f6;
                border-radius: 5px;
                margin: 5px 0;
                font-family: sans-serif;
                font-size: 12px;
            }
            .tts-status { color: #28a745; font-weight: bold; }
            .tts-error { color: #dc3545; font-weight: bold; }
            .tts-info { color: #17a2b8; }
        </style>
    </head>
    <body>
        <div id="tts-container">
            <div id="tts-status" class="tts-status">🔊 Initializing TTS System...</div>
            <div id="tts-debug" class="tts-info"></div>
        </div>
        
        <script>
        (function() {
            console.log("=== TTS Component Loading ===");
            
            // Try to access the top-level window across all iframe levels
            let targetWindow = window;
            try {
                // Navigate up the window hierarchy to find the top window
                while (targetWindow.parent && targetWindow.parent !== targetWindow) {
                    targetWindow = targetWindow.parent;
                }
                console.log("Found target window:", targetWindow === window.top ? "top window" : "parent window");
            } catch (e) {
                console.log("Using current window due to access restrictions");
                targetWindow = window;
            }
            
            // Initialize TTS in target window
            if (!targetWindow.ttsInitialized) {
                console.log("Initializing TTS system in target window...");
                
                targetWindow.ttsQueue = [];
                targetWindow.isTTSPlaying = false;
                targetWindow.ttsAudioElement = null;
                targetWindow.ttsEnabled = true;
                targetWindow.ttsInitialized = true;
                
                console.log("TTS state initialized");
                
                // Update status
                document.getElementById('tts-status').innerHTML = '🔊 TTS System Ready';
                document.getElementById('tts-debug').innerHTML = 'Functions registered in target window';
            }
            
            function playNextTTS() {
                console.log("playNextTTS called, queue length:", targetWindow.ttsQueue.length);
                
                if (targetWindow.ttsQueue.length === 0 || !targetWindow.ttsEnabled) {
                    targetWindow.isTTSPlaying = false;
                    console.log("No items in queue or TTS disabled");
                    updateStatus("Idle");
                    return;
                }
                
                targetWindow.isTTSPlaying = true;
                const audioData = targetWindow.ttsQueue.shift();
                console.log("Playing audio, data length:", audioData.length);
                updateStatus("Playing audio...");
                
                // Create audio element in target window if it doesn't exist
                if (!targetWindow.ttsAudioElement) {
                    console.log("Creating new audio element in target");
                    targetWindow.ttsAudioElement = new targetWindow.Audio();
                    
                    targetWindow.ttsAudioElement.onended = function() {
                        console.log("Audio ended, playing next");
                        targetWindow.isTTSPlaying = false;
                        setTimeout(playNextTTS, 100);
                    };
                    
                    targetWindow.ttsAudioElement.onerror = function(error) {
                        console.error("Audio playback error:", error);
                        updateStatus("Audio error: " + error.message, true);
                        targetWindow.isTTSPlaying = false;
                        setTimeout(playNextTTS, 100);
                    };
                    
                    targetWindow.ttsAudioElement.onloadstart = function() {
                        console.log("Audio load started");
                        updateStatus("Loading audio...");
                    };
                    
                    targetWindow.ttsAudioElement.oncanplay = function() {
                        console.log("Audio can play");
                        updateStatus("Audio ready");
                    };
                }
                
                // Set the audio source and play
                try {
                    const audioSrc = "data:audio/mp3;base64," + audioData;
                    console.log("Setting audio src, length:", audioSrc.length);
                    targetWindow.ttsAudioElement.src = audioSrc;
                    
                    // Try to play with user interaction handling
                    const playPromise = targetWindow.ttsAudioElement.play();
                    
                    if (playPromise !== undefined) {
                        playPromise.then(function() {
                            console.log("Audio playing successfully");
                            updateStatus("🔊 Playing");
                        }).catch(function(error) {
                            console.error("Audio play failed:", error);
                            if (error.name === 'NotAllowedError') {
                                updateStatus("⚠️ Click page to enable audio", true);
                                console.warn('Audio playback blocked by browser policy. User interaction required.');
                            } else {
                                updateStatus("Play failed: " + error.message, true);
                            }
                            targetWindow.isTTSPlaying = false;
                            setTimeout(playNextTTS, 100);
                        });
                    }
                } catch (error) {
                    console.error("Audio setup failed:", error);
                    updateStatus("Setup failed: " + error.message, true);
                    targetWindow.isTTSPlaying = false;
                    setTimeout(playNextTTS, 100);
                }
            }
            
            function updateStatus(message, isError = false) {
                const statusEl = document.getElementById('tts-status');
                if (statusEl) {
                    statusEl.innerHTML = message;
                    statusEl.className = isError ? 'tts-error' : 'tts-status';
                }
            }
            
            // Register functions in target window AND make them available to other iframes
            const ttsAPI = {
                addToTTSQueue: function(audioData) {
                    console.log("Adding to TTS queue, enabled:", targetWindow.ttsEnabled);
                    if (!targetWindow.ttsEnabled) return;
                    
                    targetWindow.ttsQueue.push(audioData);
                    console.log("Queue length after adding:", targetWindow.ttsQueue.length);
                    updateStatus(`Queued (${targetWindow.ttsQueue.length})`);
                    
                    if (!targetWindow.isTTSPlaying) {
                        console.log("Starting playback");
                        playNextTTS();
                    }
                },
                
                stopTTS: function() {
                    console.log("Stopping TTS");
                    targetWindow.ttsEnabled = false;
                    if (targetWindow.ttsAudioElement) {
                        targetWindow.ttsAudioElement.pause();
                        targetWindow.ttsAudioElement.currentTime = 0;
                    }
                    targetWindow.ttsQueue = [];
                    targetWindow.isTTSPlaying = false;
                    updateStatus("Stopped");
                    // Re-enable after short delay
                    setTimeout(function() {
                        targetWindow.ttsEnabled = true;
                        updateStatus("Ready");
                        console.log("TTS re-enabled");
                    }, 500);
                },
                
                clearTTSQueue: function() {
                    console.log("Clearing TTS queue");
                    targetWindow.ttsQueue = [];
                    updateStatus("Queue cleared");
                },
                
                getTTSQueueLength: function() {
                    return targetWindow.ttsQueue.length;
                },
                
                isTTSActive: function() {
                    return targetWindow.isTTSPlaying || targetWindow.ttsQueue.length > 0;
                },
                
                testTTS: function() {
                    console.log("Testing browser audio with simple beep");
                    updateStatus("Testing audio...");
                    try {
                        const audioContext = new (targetWindow.AudioContext || targetWindow.webkitAudioContext)();
                        const oscillator = audioContext.createOscillator();
                        const gainNode = audioContext.createGain();
                        
                        oscillator.connect(gainNode);
                        gainNode.connect(audioContext.destination);
                        
                        oscillator.frequency.setValueAtTime(440, audioContext.currentTime);
                        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.5);
                        
                        oscillator.start(audioContext.currentTime);
                        oscillator.stop(audioContext.currentTime + 0.5);
                        
                        console.log("Test beep should play now");
                        updateStatus("🔊 Test beep played");
                        setTimeout(() => updateStatus("Ready"), 2000);
                    } catch (error) {
                        console.error("Audio context test failed:", error);
                        updateStatus("Audio test failed: " + error.message, true);
                    }
                }
            };
            
            // Register functions in multiple locations for maximum compatibility
            Object.assign(targetWindow, ttsAPI);
            
            // Also register in current window for direct access
            Object.assign(window, ttsAPI);
            
            // Try to register in parent windows too
            try {
                if (window.parent && window.parent !== window) {
                    Object.assign(window.parent, ttsAPI);
                }
                if (window.top && window.top !== window) {
                    Object.assign(window.top, ttsAPI);
                }
            } catch (e) {
                console.log("Could not register in parent windows due to security restrictions");
            }
            
            console.log("=== TTS Functions Registered ===");
            console.log("Available functions:", {
                addToTTSQueue: typeof targetWindow.addToTTSQueue,
                stopTTS: typeof targetWindow.stopTTS,
                clearTTSQueue: typeof targetWindow.clearTTSQueue,
                testTTS: typeof targetWindow.testTTS
            });
            
            // Update debug info
            document.getElementById('tts-debug').innerHTML = 
                `Functions: ${Object.keys(ttsAPI).length} registered in multiple contexts`;
                
            updateStatus("🔊 TTS System Ready");
            
        })();
        </script>
    </body>
    </html>
    """

def tts_component():
    """Create a persistent TTS component that works across Streamlit reruns"""
    html_content = get_tts_component_html()
    return components.html(html_content, height=80)

def clean_text_for_tts(text: str) -> str:
    """Clean text for better TTS pronunciation"""
    # Remove markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # inline code
    text = re.sub(r'#{1,6}\s+', '', text)         # headers
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # links
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove empty parentheses and brackets
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    
    return text

def split_text_for_tts(text: str, max_chunk_size: int = 150) -> List[str]:
    """Split text into TTS-friendly chunks at natural break points"""
    if not text.strip():
        return []
    
    # First, split by major punctuation
    sentences = re.split(r'([.!?]+\s*)', text)
    
    chunks = []
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
        full_sentence = sentence + punctuation
        
        # If adding this sentence would exceed max size and we have content, emit current chunk
        if len(current_chunk + full_sentence) > max_chunk_size and current_chunk.strip():
            chunks.append(current_chunk.strip())
            current_chunk = full_sentence
        else:
            current_chunk += full_sentence
    
    # Add any remaining content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Handle very long chunks by splitting on commas or other punctuation
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chunk_size:
            final_chunks.append(chunk)
        else:
            # Split long chunks further
            sub_parts = re.split(r'([,;:\n]\s*)', chunk)
            sub_chunk = ""
            for j in range(0, len(sub_parts), 2):
                part = sub_parts[j]
                separator = sub_parts[j + 1] if j + 1 < len(sub_parts) else ""
                full_part = part + separator
                
                if len(sub_chunk + full_part) > max_chunk_size and sub_chunk.strip():
                    final_chunks.append(sub_chunk.strip())
                    sub_chunk = full_part
                else:
                    sub_chunk += full_part
            
            if sub_chunk.strip():
                final_chunks.append(sub_chunk.strip())
    
    return [chunk for chunk in final_chunks if chunk.strip()]

def enqueue_tts(text: str, lang: str = 'en'):
    """Synthesize and enqueue TTS for the given text with improved error handling"""
    if not text.strip():
        return False
        
    if not GTTs_AVAILABLE:
        st.warning("gTTS not available. Install with: pip install gtts")
        return False
    
    try:
        # Clean text for better TTS
        clean_text = clean_text_for_tts(text)
        if not clean_text:
            return False
        
        # Debug info
        st.write(f"🔊 Generating TTS for: '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}' (lang: {lang})")
        
        # Synthesize speech with language support
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        # Convert to base64
        audio_data = audio_buffer.read()
        if not audio_data:
            st.error("No audio data generated")
            return False
            
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        st.write(f"✅ Generated {len(audio_data)} bytes of audio data")
        
        # Create a unique script that tries multiple window contexts
        js_code = f"""
        <script>
        console.log('Attempting to enqueue TTS audio in multiple contexts...');
        
        function tryEnqueue() {{
            const contexts = [window, window.parent, window.top];
            
            for (let i = 0; i < contexts.length; i++) {{
                try {{
                    const ctx = contexts[i];
                    if (ctx && ctx.addToTTSQueue && typeof ctx.addToTTSQueue === 'function') {{
                        console.log('Found addToTTSQueue in context ' + i + ', calling...');
                        ctx.addToTTSQueue('{audio_b64}');
                        console.log('TTS audio enqueued successfully in context ' + i);
                        return true;
                    }}
                }} catch (e) {{
                    console.log('Context ' + i + ' failed:', e.message);
                }}
            }}
            
            console.error('addToTTSQueue function not found in any context!');
            return false;
        }}
        
        // Try immediately and also after a short delay
        if (!tryEnqueue()) {{
            setTimeout(function() {{
                console.log('Retrying TTS enqueue after delay...');
                tryEnqueue();
            }}, 500);
        }}
        </script>
        """
        components.html(js_code, height=0)
        return True
        
    except Exception as e:
        st.error(f"TTS synthesis failed: {str(e)}")
        import traceback
        st.error(f"Full traceback: {traceback.format_exc()}")
        return False

def enqueue_text_chunks_for_tts(text: str, lang: str = 'en'):
    """Split text into chunks and enqueue each for TTS"""
    if not text.strip() or not GTTs_AVAILABLE:
        return 0
    
    chunks = split_text_for_tts(text)
    successful_chunks = 0
    
    for chunk in chunks:
        if enqueue_tts(chunk, lang):
            successful_chunks += 1
            # Small delay between chunks to prevent overwhelming the API
            time.sleep(0.1)
    
    return successful_chunks

def stop_tts():
    """Stop any currently playing TTS and clear the queue"""
    js_code = """
    <script>
    try {
        if (window.stopTTS) {
            window.stopTTS();
        }
    } catch (error) {
        console.error('Failed to stop TTS:', error);
    }
    </script>
    """
    components.html(js_code, height=0)

def clear_tts_queue():
    """Clear the TTS queue without stopping current playback"""
    js_code = """
    <script>
    try {
        if (window.clearTTSQueue) {
            window.clearTTSQueue();
        }
    } catch (error) {
        console.error('Failed to clear TTS queue:', error);
    }
    </script>
    """
    components.html(js_code, height=0)

# --------------------------
# Vera singleton
# --------------------------
@st.cache_resource
def get_vera():
    return Vera()

# --------------------------
# Content extraction & rendering
# --------------------------
def is_real_file(path: str) -> bool:
    """Treat path as a file only if it exists on disk (avoid false positives)."""
    try:
        # Normalize path: expanduser, remove surrounding punctuation
        p = os.path.expanduser(path.strip())
        return os.path.exists(p)
    except Exception:
        return False

def extract_content_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract code blocks, JSON, URLs, and existing file paths."""
    blocks: List[Dict[str, Any]] = []

    # Code fences
    code_pattern = r'```(\w+)?\s*(.*?)```'
    for m in re.finditer(code_pattern, text, re.DOTALL):
        lang = m.group(1) or "text"
        code = m.group(2).strip()
        blocks.append({"type": "code", "language": lang, "content": code, "start": m.start(), "end": m.end()})

    # JSON fragments (attempt to parse substrings that look like JSON)
    json_pattern = r'(\{(?:[^{}]|\{[^{}]*\})*\}|\[(?:[^\[\]]|\[[^\[\]]*\])*\])'
    for m in re.finditer(json_pattern, text, re.DOTALL):
        snippet = m.group(1)
        try:
            parsed = json.loads(snippet)
            blocks.append({"type": "json", "content": parsed, "start": m.start(), "end": m.end()})
        except Exception:
            pass

    # URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
    for m in re.finditer(url_pattern, text):
        url = m.group(0)
        blocks.append({"type": "url", "content": url, "start": m.start(), "end": m.end()})

    # File candidates beginning with / or ./ or ~/ or Windows drive letter like C:\ (simple)
    # But only treat as file if exists.
    file_pattern = r'((?:\~|\.\/|\/|[A-Za-z]:\\)[^\s]+)'
    for m in re.finditer(file_pattern, text):
        fp = m.group(1)
        try_path = os.path.expanduser(fp)
        if is_real_file(try_path):
            blocks.append({"type": "file", "content": try_path, "start": m.start(), "end": m.end()})

    blocks.sort(key=lambda x: x['start'])
    return blocks

def render_content_with_blocks(text: str, blocks: List[Dict[str, Any]]):
    """Render text by interleaving plain text and block renderers (code, json, url, file)."""
    if not blocks:
        st.markdown(text)
        return

    last = 0
    for b in blocks:
        if b['start'] > last:
            st.markdown(text[last:b['start']])
        if b['type'] == 'code':
            with st.expander(f"Code block ({b.get('language','text')})", expanded=False):
                st.code(b['content'], language=b.get('language','text'))
        elif b['type'] == 'json':
            with st.expander("JSON content", expanded=False):
                st.json(b['content'])
        elif b['type'] == 'url':
            url = b['content']
            domain = urlparse(url).netloc
            with st.expander(f"URL: {domain}", expanded=False):
                st.markdown(f"[Open link]({url})")
        elif b['type'] == 'file':
            fp = b['content']
            with st.expander(f"File: {fp}", expanded=False):
                try:
                    # text preview for small files
                    size = os.path.getsize(fp)
                    if size < 5_000_000:  # 5 MB limit to preview
                        with open(fp, "rb") as fh:
                            data = fh.read()
                        try:
                            text_preview = data.decode("utf-8")
                            st.text_area("File preview", text_preview, height=300)
                            st.download_button("Download file", data=data, file_name=os.path.basename(fp))
                        except Exception:
                            st.download_button("Download file", data=data, file_name=os.path.basename(fp))
                    else:
                        with open(fp, "rb") as fh:
                            data = fh.read(1024)
                        st.text(f"Large file ({size} bytes). Showing start only:\n{data[:500]!r}")
                        st.download_button("Download large file", data=open(fp, "rb"), file_name=os.path.basename(fp))
                except Exception as e:
                    st.text(f"Cannot open file: {e}")
        last = b['end']

    if last < len(text):
        st.markdown(text[last:])

# --------------------------
# Helpers for STT
# --------------------------
def transcribe_audio_placeholder(audio_bytes: bytes) -> str:
    """
    Placeholder for STT transcription.
    Replace with your transcription backend (OpenAI Whisper, local Whisper, etc.).
    This function should return the transcribed text string.
    """
    # Example: raise NotImplementedError or return empty string.
    # Implementor: use Whisper or OpenAI's transcription API to return result.
    raise NotImplementedError("Please wire transcribe_audio_placeholder() to a transcription backend.")

# --------------------------
# Enhanced Chat UI class
# --------------------------
class ChatUI:
    def __init__(self, vera: Vera):
        self.vera = vera
        st.set_page_config(page_title="Vera Chat", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")
        self.init_state()
        tts_component()  # Initialize TTS component

    def init_state(self):
        if 'messages' not in st.session_state:
            st.session_state.messages = []  # list of {"id","role","content"}
        if 'processing' not in st.session_state:
            st.session_state.processing = False
        if 'files' not in st.session_state:
            st.session_state.files = {}  # filename -> bytes
        if 'counter' not in st.session_state:
            st.session_state.counter = 0
        if 'tts_enabled' not in st.session_state:
            st.session_state.tts_enabled = True
        if 'tts_language' not in st.session_state:
            st.session_state.tts_language = 'en'
        if 'tts_chunk_responses' not in st.session_state:
            st.session_state.tts_chunk_responses = True

    def render_sidebar(self):
        with st.sidebar:
            st.title("Vera Controls")
            if st.button("Clear chat"):
                st.session_state.messages = []
                clear_tts_queue()
                
            # Enhanced TTS controls
            st.markdown("### Text-to-Speech")
            if GTTs_AVAILABLE:
                st.session_state.tts_enabled = st.checkbox("Enable TTS", value=st.session_state.tts_enabled)
                
                # Language selection
                tts_languages = {
                    'en': 'English',
                    'es': 'Spanish', 
                    'fr': 'French',
                    'de': 'German',
                    'it': 'Italian',
                    'pt': 'Portuguese',
                    'ja': 'Japanese',
                    'ko': 'Korean',
                    'zh': 'Chinese'
                }
                
                selected_lang = st.selectbox(
                    "TTS Language",
                    options=list(tts_languages.keys()),
                    format_func=lambda x: tts_languages[x],
                    index=list(tts_languages.keys()).index(st.session_state.tts_language)
                )
                st.session_state.tts_language = selected_lang
                
                st.session_state.tts_chunk_responses = st.checkbox(
                    "Stream TTS (speak while typing)", 
                    value=st.session_state.tts_chunk_responses,
                    help="Speak response chunks as they're generated, or wait for complete response"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Stop TTS"):
                        stop_tts()
                with col2:
                    if st.button("Clear Queue"):
                        clear_tts_queue()
                        
                # Test TTS
                if st.button("Test TTS"):
                    test_text = "Hello! This is a test of the text to speech system."
                    if enqueue_tts(test_text, st.session_state.tts_language):
                        st.success("TTS test queued! Check browser console for debug info.")
                    else:
                        st.error("TTS test failed!")
                
                # Audio test button
                if st.button("Test Browser Audio"):
                    js_test = """
                    <script>
                    console.log('Testing browser audio capabilities...');
                    
                    function tryTest() {
                        const contexts = [window, window.parent, window.top];
                        
                        for (let i = 0; i < contexts.length; i++) {
                            try {
                                const ctx = contexts[i];
                                if (ctx && ctx.testTTS && typeof ctx.testTTS === 'function') {
                                    console.log('Found testTTS in context ' + i + ', calling...');
                                    ctx.testTTS();
                                    return true;
                                }
                            } catch (e) {
                                console.log('Context ' + i + ' testTTS failed:', e.message);
                            }
                        }
                        
                        console.error('testTTS function not found in any context!');
                        return false;
                    }
                    
                    if (!tryTest()) {
                        setTimeout(function() {
                            console.log('Retrying testTTS after delay...');
                            tryTest();
                        }, 500);
                    }
                    </script>
                    """
                    components.html(js_test, height=0)
                    st.info("Audio test triggered - check browser console and listen for beep")
                
                # Simple audio test
                if st.button("Test Simple Audio"):
                    js_simple_test = """
                    <script>
                    console.log('Testing simple audio...');
                    
                    function trySimpleTest() {
                        const contexts = [window, window.parent, window.top];
                        
                        for (let i = 0; i < contexts.length; i++) {
                            try {
                                const ctx = contexts[i];
                                if (ctx && ctx.testSimpleAudio && typeof ctx.testSimpleAudio === 'function') {
                                    console.log('Found testSimpleAudio in context ' + i + ', calling...');
                                    ctx.testSimpleAudio();
                                    return true;
                                }
                            } catch (e) {
                                console.log('Context ' + i + ' testSimpleAudio failed:', e.message);
                            }
                        }
                        
                        console.error('testSimpleAudio function not found in any context!');
                        return false;
                    }
                    
                    trySimpleTest();
                    </script>
                    """
                    components.html(js_simple_test, height=0)
                    st.info("Simple audio test triggered")
                
                # Debug info
                if st.button("Debug TTS Status"):
                    js_debug = """
                    <script>
                    console.log('=== TTS DEBUG INFO ===');
                    console.log('TTS Enabled:', window.ttsEnabled);
                    console.log('Currently Playing:', window.isTTSPlaying);  
                    console.log('Queue Length:', window.ttsQueue ? window.ttsQueue.length : 'undefined');
                    console.log('Audio Element:', window.ttsAudioElement);
                    console.log('Functions available:', {
                        addToTTSQueue: typeof window.addToTTSQueue,
                        stopTTS: typeof window.stopTTS,
                        testTTS: typeof window.testTTS
                    });
                    </script>
                    """
                    components.html(js_debug, height=0)
                    st.info("Debug info logged to browser console - open Developer Tools (F12)")
            else:
                st.warning("TTS unavailable: install gTTS with `pip install gtts`")
                
            st.markdown("### Uploaded files")
            if st.session_state.files:
                for name, info in st.session_state.files.items():
                    st.write(f"- {name} ({info['size']} bytes)")
                    if st.button(f"Remove {name}", key=f"rm_{name}"):
                        st.session_state.files.pop(name, None)
                        st.rerun()
            else:
                st.write("No files uploaded yet.")

            st.markdown("---")
            st.markdown("Drag files onto the uploader below to add to the session (they will be available for assistant to reference).")
            uploaded = st.file_uploader("Drop files here", accept_multiple_files=True, key="uploader")
            if uploaded:
                for f in uploaded:
                    data = f.read()
                    st.session_state.files[f.name] = {"data": data, "size": len(data), "name": f.name}
                st.rerun()  # re-render sidebar with new files listed

            st.markdown("---")
            st.markdown("Export chat:")
            if st.button("Export JSON"):
                chat_data = {
                    "messages": st.session_state.messages,
                    "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_messages": len(st.session_state.messages)
                }
                st.download_button(
                    "Download chat as JSON", 
                    json.dumps(chat_data, indent=2), 
                    file_name=f"vera_chat_{int(time.time())}.json", 
                    mime="application/json"
                )

    def display_history(self):
        """Render finalized messages from session_state.messages"""
        for msg in st.session_state.messages:
            with st.chat_message(msg['role']):
                # render final content with blocks
                blocks = extract_content_blocks(msg['content'])
                render_content_with_blocks(msg['content'], blocks)

    def process_user_input(self, user_input: str):
        if not user_input or st.session_state.processing:
            return

        st.session_state.processing = True
        st.session_state.counter += 1
        id_num = st.session_state.counter

        # Append user message (finalized immediately)
        st.session_state.messages.append({"id": f"u{id_num}", "role": "user", "content": user_input})
        # Rerun will display it, but we also show it below in the streaming area to keep layout consistent.

        # Create a placeholder area right below history for streaming updates
        stream_area = st.empty()   # will contain user + assistant streaming bubble
        
        # Render the user message and an initial assistant placeholder
        with stream_area.container():
            # show the user bubble (again) so streaming appears immediately below it
            with st.chat_message("user"):
                st.markdown(user_input)

            # assistant streaming bubble placeholder
            assistant_placeholder = st.empty()
            with assistant_placeholder.container():
                with st.chat_message("assistant"):
                    st.markdown("_Vera is thinking..._")

        # Enhanced streaming loop with better TTS chunking
        final_collected = ""
        tts_buffer = ""  # Buffer for TTS chunks
        last_tts_position = 0  # Track what we've already sent to TTS

        try:
            # gen = self.vera.stream_llm_with_memory(self.vera.deep_llm, user_input)
            gen = self.vera.async_run(user_input)
            for chunk in gen:
                if chunk is None:
                    continue
                    
                # Append chunk
                final_collected += str(chunk)
                tts_buffer += str(chunk)

                # Update assistant live in placeholder (plain markdown to avoid heavy parsing)
                with stream_area.container():
                    with st.chat_message("user"):
                        st.markdown(user_input)
                    with st.chat_message("assistant"):
                        st.markdown(final_collected)

                # Enhanced TTS chunking logic
                if (st.session_state.tts_enabled and 
                    st.session_state.tts_chunk_responses and 
                    GTTs_AVAILABLE):
                    
                    # Look for natural sentence breaks
                    sentences = re.split(r'([.!?]+\s+)', tts_buffer)
                    
                    # If we have complete sentences, process them
                    if len(sentences) > 2:  # At least one complete sentence
                        # Keep the last incomplete part
                        complete_part = ''.join(sentences[:-1])
                        remaining_part = sentences[-1]
                        
                        if complete_part.strip():
                            # Send complete sentences to TTS
                            enqueue_tts(complete_part.strip(), st.session_state.tts_language)
                            tts_buffer = remaining_part

            # finalization: append assistant to history as finalized message
            final_text = final_collected.strip() or "(no content)"
            st.session_state.messages.append({"id": f"a{id_num}", "role": "assistant", "content": final_text})

            # Handle final TTS - either remaining buffer or complete response
            if st.session_state.tts_enabled and GTTs_AVAILABLE:
                if st.session_state.tts_chunk_responses:
                    # Send any remaining buffer
                    if tts_buffer.strip():
                        enqueue_tts(tts_buffer.strip(), st.session_state.tts_language)
                else:
                    # Send complete response as chunks
                    enqueue_text_chunks_for_tts(final_text, st.session_state.tts_language)

        except Exception as e:
            err = f"Error generating response: {e}"
            with stream_area.container():
                with st.chat_message("assistant"):
                    st.markdown(err)
            st.session_state.messages.append({"id": f"a{id_num}", "role": "assistant", "content": err})
        finally:
            st.session_state.processing = False
            # Clear the temporary stream area to allow history to be shown by normal display_history
            stream_area.empty()
            # Rerun so history shows finalized assistant bubble
            st.rerun()

    def run(self):
        # Sidebar and header
        self.render_sidebar()
        st.title("Vera Chat Interface")
        st.caption("Ask Vera — speech in/out, files and links supported")

        # Display finalized chat history
        self.display_history()

        st.divider()
        if 'current_session_id' not in st.session_state:
            st.session_state.current_session_id = self.vera.sess.id

        st.title("Conversation Graph Panel Demo")

        # --- Session Info UI ---
        with st.container():
            st.markdown("#### 🧩 Session Information")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text_input(
                    "Current Session ID",
                    value=st.session_state.current_session_id,
                    disabled=True,
                )
            with col2:
                if st.button("🔄 Refresh Session"):
                    st.session_state.current_session_id = self.vera.sess.id
                    st.success("Session ID reloaded")

        # # --- Graph Controls ---
        # graph_panel = ConversationGraphPanel(
        #     st.session_state.current_session_id,
        #     memory_system=self.vera.mem
        # )

        # auto_refresh = st.toggle("Auto-refresh", value=False)

        # if auto_refresh:
        #     st.info("Graph will auto-refresh every 10 seconds.")
        #     graph_panel.auto_update(interval=10, height=500)
        # else:
        #     graph_panel.render(height=500)

        # st.set_page_config(page_title="Dynamic Graph Panel", layout="wide")

        st.header("Conversation Memory Visualization")

        # Example: you already have a session selector in your UI
        session_id = self.vera.sess.id

        if session_id:
            # Create and render the graph component
            panel = ConversationGraphPanel(session_id, memory_system=self.vera.mem, refresh_interval=5)
            panel.render()

        # Bottom controls: STT button (if available), audio upload fallback, and chat_input
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            # In-browser recording if st_audiorec is installed
            stt_text = None
            try:
                from st_audiorec import st_audiorec  # optional dependency
                audio_bytes = st_audiorec()
                if audio_bytes is not None:
                    st.info("Audio recorded — transcribing (you must wire a transcription backend).")
                    try:
                        # If you have a transcription backend, call it here and set stt_text
                        # stt_text = transcribe_audio_placeholder(audio_bytes)
                        pass
                    except Exception as e:
                        st.warning(f"Transcription failed: {e}")
            except Exception:
                # File upload fallback
                audio_file = st.file_uploader("Upload audio for STT (optional)", type=["wav", "mp3", "m4a"])
                if audio_file is not None:
                    st.info("Audio uploaded. Click 'Transcribe & Send' to transcribe and send to Vera.")
                    if st.button("Transcribe & Send"):
                        try:
                            audio_bytes = audio_file.read()
                            # Replace with your transcription implementation
                            stt_text = transcribe_audio_placeholder(audio_bytes)
                            if stt_text:
                                self.process_user_input(stt_text)
                        except NotImplementedError as nie:
                            st.error("Transcription not implemented. Please implement transcribe_audio_placeholder().")
                        except Exception as e:
                            st.error(f"Transcription error: {e}")

            user_input = st.chat_input("Type your message here...", disabled=st.session_state.processing)

        with col2:
            if st.button("🔇 Stop TTS", help="Stop current speech"):
                stop_tts()
            if st.button("🗑️ Clear Queue", help="Clear speech queue"):
                clear_tts_queue()

        # Process user input
        if user_input:
            self.process_user_input(user_input)

# --------------------------
# Entrypoint
# --------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
    from vera import Vera
    vera = get_vera()
    ui = ChatUI(vera)
    ui.run()