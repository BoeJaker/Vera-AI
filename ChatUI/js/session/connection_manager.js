// connectionManager.js - Add to your frontend

class ConnectionManager {
    constructor() {
        this.sessionId = null;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isInitializing = false;
        this.initPromise = null;
        this.messageHandlers = [];
    }

    async initSession() {
        // Prevent duplicate initialization
        if (this.isInitializing) {
            console.log('Session initialization already in progress...');
            return this.initPromise;
        }

        // Check if we have a valid existing session
        if (this.sessionId) {
            const isValid = await this.validateSession();
            if (isValid) {
                console.log('Using existing valid session:', this.sessionId);
                return { sessionId: this.sessionId, status: 'existing' };
            }
        }

        // Check localStorage for previous session
        const storedSessionId = localStorage.getItem('vera_session_id');
        if (storedSessionId) {
            const isValid = await this.validateSession(storedSessionId);
            if (isValid) {
                this.sessionId = storedSessionId;
                console.log('Resumed session from storage:', this.sessionId);
                await this.connectWebSocket();
                return { sessionId: this.sessionId, status: 'resumed' };
            } else {
                localStorage.removeItem('vera_session_id');
            }
        }

        // Create new session
        this.isInitializing = true;
        this.initPromise = this._createNewSession();
        
        try {
            const result = await this.initPromise;
            return result;
        } finally {
            this.isInitializing = false;
            this.initPromise = null;
        }
    }

    async _createNewSession() {
        try {
            console.log('Creating new session...');
            const response = await fetch('/api/session/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`Session creation failed: ${response.statusText}`);
            }

            const data = await response.json();
            this.sessionId = data.session_id;
            localStorage.setItem('vera_session_id', this.sessionId);
            
            console.log('Session created:', this.sessionId);
            
            // Connect WebSocket
            await this.connectWebSocket();
            
            return data;
        } catch (error) {
            console.error('Failed to create session:', error);
            throw error;
        }
    }

    async validateSession(sessionId = this.sessionId) {
        if (!sessionId) return false;

        try {
            const response = await fetch(`/api/session/${sessionId}/status`);
            const data = await response.json();
            return data.exists === true;
        } catch (error) {
            console.error('Session validation failed:', error);
            return false;
        }
    }

    async connectWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        return new Promise((resolve, reject) => {
            try {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/api/session/${this.sessionId}/ws`;
                
                console.log('Connecting WebSocket:', wsUrl);
                this.websocket = new WebSocket(wsUrl);

                this.websocket.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    resolve();
                };

                this.websocket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };

                this.websocket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };

                this.websocket.onclose = () => {
                    console.log('WebSocket closed');
                    this.attemptReconnect();
                };

                // Timeout after 10 seconds
                setTimeout(() => {
                    if (this.websocket.readyState !== WebSocket.OPEN) {
                        reject(new Error('WebSocket connection timeout'));
                    }
                }, 10000);

            } catch (error) {
                reject(error);
            }
        });
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.notifyConnectionLost();
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(async () => {
            try {
                await this.connectWebSocket();
            } catch (error) {
                console.error('Reconnection failed:', error);
            }
        }, delay);
    }

    handleMessage(data) {
        console.log('WebSocket message:', data);
        
        // Call all registered handlers
        this.messageHandlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('Message handler error:', error);
            }
        });
    }

    onMessage(handler) {
        this.messageHandlers.push(handler);
    }

    notifyConnectionLost() {
        // Show user-friendly error
        const event = new CustomEvent('vera-connection-lost', {
            detail: { sessionId: this.sessionId }
        });
        window.dispatchEvent(event);
    }

    async endSession() {
        if (!this.sessionId) return;

        try {
            if (this.websocket) {
                this.websocket.close();
            }

            await fetch(`/api/session/${this.sessionId}/end`, {
                method: 'POST'
            });

            localStorage.removeItem('vera_session_id');
            this.sessionId = null;
            this.websocket = null;
            
        } catch (error) {
            console.error('Failed to end session:', error);
        }
    }
}

// Global singleton
window.connectionManager = new ConnectionManager();