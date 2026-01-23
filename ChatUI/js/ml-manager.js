// ml-manager.js - Frontend for ML Tab (DEBUG VERSION)

(() => {
VeraChat.prototype.initML = function() {
    console.log('[ML] Initializing ML tab');
    
    // Just use a simple fixed ID for this browser session
    if (!this.mlSessionId) {
        this.mlSessionId = 'ttt-game-' + Date.now();
    }
    
    console.log('[ML] Using game ID:', this.mlSessionId);
    
    this.cryptoInterval = null;
    this.currentTTTGame = null;
    
    this.testMLAPI();
};
    
    VeraChat.prototype.testMLAPI = async function() {
        try {
            console.log('[ML] Testing ML API...');
            const response = await fetch('http://llm.int:8888/api/ml/test');
            if (response.ok) {
                const data = await response.json();
                console.log('[ML] ✅ API test successful:', data);
                // Now that we know API works, init the game
                this.initTicTacToe();
                this.loadMLStats();
            } else {
                console.error('[ML] ❌ API test failed:', response.status);
                this.showMLError('ML API not available. Make sure the backend is running.');
            }
        } catch (error) {
            console.error('[ML] ❌ API test error:', error);
            this.showMLError('Cannot connect to ML API. Check server logs.');
        }
    };
    
    VeraChat.prototype.showMLError = function(message) {
        const board = document.getElementById('ttt-board');
        if (board) {
            board.innerHTML = `
                <div style="grid-column: 1 / -1; padding: 20px; text-align: center; color: var(--danger);">
                    <h3>⚠️ Error</h3>
                    <p>${message}</p>
                    <button onclick="app.testMLAPI()" style="margin-top: 10px; padding: 8px 16px; background: var(--accent); border: none; border-radius: 4px; color: white; cursor: pointer;">
                        Retry
                    </button>
                </div>
            `;
        }
    };
    
    VeraChat.prototype.switchMLPanel = function(panel) {
        document.querySelectorAll('.ml-panel').forEach(p => p.style.display = 'none');
        document.querySelectorAll('.ml-nav-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.style.background = 'var(--bg-darker)';
            btn.style.color = 'var(--text)';
        });
        
        document.getElementById(`ml-panel-${panel}`).style.display = 'block';
        const activeBtn = document.querySelector(`.ml-nav-btn[data-panel="${panel}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.style.background = 'var(--accent)';
            activeBtn.style.color = 'white';
        }
    };
    
    // ==================== TIC-TAC-TOE ====================
  VeraChat.prototype.initTicTacToe = async function() {
    console.log('[TTT] ==================== INIT GAME ====================');
    console.log('[TTT] mlSessionId:', this.mlSessionId);
    console.log('[TTT] Type:', typeof this.mlSessionId);
    
    const board = document.getElementById('ttt-board');
    if (!board) {
        console.error('[TTT] ❌ Board element not found!');
        return;
    }
    
    // Create board cells
    board.innerHTML = '';
    
    // Store reference to this for the closure
    const self = this;
    
    for (let i = 0; i < 9; i++) {
        const cell = document.createElement('div');
        cell.className = 'ttt-cell';
        cell.dataset.index = i;
        
        // Use self instead of this in the closure
        cell.onclick = function() {
            console.log('[TTT] Cell clicked. self.mlSessionId:', self.mlSessionId);
            self.handleTTTMove(i);
        };
        
        board.appendChild(cell);
    }
    
    // Start new game
    try {
        const url = `http://llm.int:8888/api/ml/tictactoe/new?session_id=${encodeURIComponent(this.mlSessionId)}`;
        console.log('[TTT] 🔵 Creating game at URL:', url);
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        console.log('[TTT] Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('[TTT] ❌ Error creating game:', errorText);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('[TTT] ✅ Game created successfully:', data);
        
        this.currentTTTGame = data;
        console.log('[TTT] Stored game state:', this.currentTTTGame);
        
        this.updateTTTBoard(data);
        this.loadMLStats();
        
        // Update message
        const msg = document.getElementById('ttt-message');
        if (msg) {
            msg.textContent = 'Your turn (○)';
            msg.style.color = 'var(--text)';
        }
        
        console.log('[TTT] ==================================================');
        
    } catch (error) {
        console.error('[TTT] ❌ Error starting game:', error);
        this.showMLError('Failed to start game: ' + error.message);
    }
};
    VeraChat.prototype.handleTTTMove = async function(position) {
        console.log('[TTT] ==================== HANDLE MOVE ====================');
        console.log('[TTT] Position clicked:', position);
        console.log('[TTT] mlSessionId:', this.mlSessionId);
        console.log('[TTT] typeof mlSessionId:', typeof this.mlSessionId);
        
        // SAFETY CHECK - make sure mlSessionId exists!
        if (!this.mlSessionId || this.mlSessionId === 'undefined') {
            console.error('[TTT] ❌ mlSessionId is invalid!');
            console.error('[TTT] Attempting to fix by using main sessionId:', this.sessionId);
            this.mlSessionId = this.sessionId || 'ttt-' + Date.now();
            console.log('[TTT] Fixed mlSessionId to:', this.mlSessionId);
        }
        
        if (!this.currentTTTGame) {
            console.error('[TTT] ❌ No active game!');
            this.showMLError('No active game. Click "New Game" to start.');
            return;
        }
        
        if (this.currentTTTGame.game_over) {
            console.log('[TTT] ⚠️ Game is over');
            return;
        }
        
        const board = this.currentTTTGame.board;
        if (board[position] !== 0) {
            console.log('[TTT] ⚠️ Position already taken');
            return;
        }
        
        try {
            const requestBody = {
                session_id: this.mlSessionId,
                position: position
            };
            
            console.log('[TTT] 🔵 Sending move request:', requestBody);
            console.log('[TTT] Request body JSON:', JSON.stringify(requestBody));
            console.log('[TTT] session_id value:', requestBody.session_id);
            console.log('[TTT] session_id type:', typeof requestBody.session_id);
            
            
            const response = await fetch('http://llm.int:8888/api/ml/tictactoe/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            console.log('[TTT] Response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('[TTT] ❌ Error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            console.log('[TTT] ✅ Move response:', data);
            
            this.currentTTTGame = data;
            this.updateTTTBoard(data);
            
            if (data.game_over) {
                this.handleTTTGameOver(data);
            }
            
            if (data.ai_confidence) {
                const confEl = document.getElementById('ttt-confidence');
                if (confEl) {
                    confEl.textContent = `AI confidence: ${(data.ai_confidence * 100).toFixed(1)}%`;
                }
            }
            
            console.log('[TTT] ====================================================');
            
        } catch (error) {
            console.error('[TTT] ❌ Error making move:', error);
            this.showMLError('Error making move: ' + error.message);
        }
    };
    
    VeraChat.prototype.updateTTTBoard = function(gameState) {
        if (!gameState) {
            console.warn('[TTT] updateTTTBoard called with null/undefined gameState');
            return;
        }
        
        const cells = document.querySelectorAll('.ttt-cell');
        cells.forEach((cell, i) => {
            const value = gameState.board[i];
            cell.textContent = value === 1 ? '✕' : value === -1 ? '○' : '';
            cell.classList.toggle('filled', value !== 0);
            cell.classList.remove('win');
        });
        
        const msg = document.getElementById('ttt-message');
        if (msg && gameState.message) {
            msg.textContent = gameState.message;
        }
    };
    
    VeraChat.prototype.handleTTTGameOver = function(gameState) {
        const msg = document.getElementById('ttt-message');
        
        if (gameState.winning_line) {
            gameState.winning_line.forEach(i => {
                const cell = document.querySelector(`.ttt-cell[data-index="${i}"]`);
                if (cell) cell.classList.add('win');
            });
        }
        
        if (msg) {
            if (gameState.winner === 1) {
                msg.style.color = '#f44336';
            } else if (gameState.winner === -1) {
                msg.style.color = '#4CAF50';
            } else {
                msg.style.color = 'var(--text-muted)';
            }
        }
        
        this.loadMLStats();
    };
    
    VeraChat.prototype.resetTicTacToe = function() {
        console.log('[TTT] Resetting game...');
        this.initTicTacToe();
    };
    
    VeraChat.prototype.loadMLStats = async function() {
        try {
            const response = await fetch('http://llm.int:8888/api/ml/tictactoe/stats');
            if (!response.ok) {
                console.error('[ML] Failed to load stats:', response.status);
                return;
            }
            
            const stats = await response.json();
            
            const elements = {
                'ttt-ai-wins': stats.ai_wins,
                'ttt-human-wins': stats.human_wins,
                'ttt-draws': stats.draws,
                'ttt-games': stats.total_games,
                'ttt-win-rate': stats.ai_win_rate.toFixed(1) + '%'
            };
            
            for (const [id, value] of Object.entries(elements)) {
                const el = document.getElementById(id);
                if (el) el.textContent = value;
            }
            
        } catch (error) {
            console.error('[ML] Error loading stats:', error);
        }
    };
    
    // ==================== CRYPTO PREDICTOR ====================
    
    VeraChat.prototype.startCryptoPredictor = async function() {
        const symbol = document.getElementById('crypto-symbol').value;
        const timeframe = document.getElementById('crypto-timeframe').value;
        
        document.getElementById('crypto-start-btn').disabled = true;
        document.getElementById('crypto-stop-btn').disabled = false;
        document.getElementById('crypto-status').textContent = 'Learning...';
        document.getElementById('ml-status-text').textContent = 'Training';
        document.getElementById('ml-status-indicator').style.background = 'var(--success)';
        
        this.cryptoSymbol = symbol;
        this.cryptoTimeframe = timeframe;
        this.cryptoRunning = true;
        
        this.runCryptoPredictor();
    };
    
    VeraChat.prototype.runCryptoPredictor = async function() {
        if (!this.cryptoRunning) return;
        
        try {
            const response = await fetch('http://llm.int:8888/api/ml/crypto/train-step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: this.cryptoSymbol,
                    timeframe: this.cryptoTimeframe,
                    limit: 300
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update UI
            document.getElementById('crypto-accuracy-val').textContent = 
                data.accuracy.toFixed(1) + '%';
            document.getElementById('crypto-predictions').textContent = 
                data.total_predictions;
            
            if (data.results && data.results.length > 0) {
                const latest = data.results[data.results.length - 1];
                document.getElementById('crypto-current-price').textContent = 
                    '$' + latest.price.toFixed(2);
                document.getElementById('crypto-next-pred').textContent = 
                    latest.prediction === 1 ? '📈 UP' : '📉 DOWN';
                
                this.updateCryptoHistory(data.results);
            }
            
        } catch (error) {
            console.error('[Crypto] Error:', error);
            this.stopCryptoPredictor();
            alert('Crypto predictor error: ' + error.message);
        }
        
        // Run again in 60 seconds
        if (this.cryptoRunning) {
            setTimeout(() => this.runCryptoPredictor(), 60000);
        }
    };
    
    VeraChat.prototype.stopCryptoPredictor = function() {
        this.cryptoRunning = false;
        
        document.getElementById('crypto-start-btn').disabled = false;
        document.getElementById('crypto-stop-btn').disabled = true;
        document.getElementById('crypto-status').textContent = 'Stopped';
        document.getElementById('ml-status-text').textContent = 'Ready';
        document.getElementById('ml-status-indicator').style.background = 'var(--text-muted)';
    };
    
    VeraChat.prototype.updateCryptoHistory = function(results) {
        const container = document.getElementById('crypto-history');
        if (!container) return;
        
        container.innerHTML = results.slice().reverse().map(p => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--bg); border-radius: 6px; margin-bottom: 8px;">
                <div style="flex: 1;">
                    <div style="font-size: 12px; color: var(--text-muted);">
                        ${new Date().toLocaleTimeString()}
                    </div>
                    <div style="font-size: 14px; font-weight: 600;">
                        $${p.price.toFixed(2)}
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 20px;">
                        ${p.prediction === 1 ? '📈' : '📉'}
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted);">
                        ${(p.probability * 100).toFixed(1)}%
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; ${p.correct ? 'background: rgba(76, 175, 80, 0.2); color: #4CAF50;' : 'background: rgba(244, 67, 54, 0.2); color: #f44336;'}">
                        ${p.correct ? '✓ Correct' : '✗ Wrong'}
                    </div>
                </div>
            </div>
        `).join('');
    };
    
})();