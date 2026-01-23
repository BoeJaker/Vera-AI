# ml_backend.py - Machine Learning Backend for Vera AI (ENHANCED)

import numpy as np
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile, File
import traceback
import json
from datetime import datetime

router = APIRouter(prefix="/api/ml", tags=["ml"])

# =========================
# Tic-Tac-Toe Game Logic (UNCHANGED)
# =========================

WIN_LINES = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def winner(board):
    """Check if there's a winner"""
    for a,b,c in WIN_LINES:
        if board[a] == board[b] == board[c] != 0:
            return board[a]
    return 0

def check_draw(board):
    """Check if game is a draw"""
    return 0 not in board and winner(board) == 0

# =========================
# Neural Network (Policy) (UNCHANGED)
# =========================

def softmax(x):
    x = x - np.max(x)
    e = np.exp(x)
    return e / np.sum(e)

class PolicyNet:
    def __init__(self):
        np.random.seed(1)
        self.W1 = np.random.randn(9, 18) * 0.1
        self.b1 = np.zeros(18)
        self.W2 = np.random.randn(18, 9) * 0.1
        self.b2 = np.zeros(9)
        self.memory = []

    def forward(self, x):
        h = np.tanh(x @ self.W1 + self.b1)
        logits = h @ self.W2 + self.b2
        return softmax(logits), h

    def choose_move(self, board):
        board_array = np.array(board, dtype=float)
        probs, h = self.forward(board_array)
        probs = probs * (board_array == 0)
        
        if np.sum(probs) == 0:
            legal_moves = [i for i, val in enumerate(board) if val == 0]
            if legal_moves:
                action = np.random.choice(legal_moves)
                probs = np.zeros(9)
                probs[action] = 1.0
            else:
                action = 0
        else:
            probs = probs / np.sum(probs)
            action = np.random.choice(9, p=probs)
        
        self.memory.append((board_array.copy(), probs, action, h))
        return action, probs[action]

    def learn(self, reward, lr=0.05):
        for state, probs, action, h in self.memory:
            dlog = -probs
            dlog[action] += 1
            dlog *= reward

            dW2 = np.outer(h, dlog)
            db2 = dlog

            dh = dlog @ self.W2.T
            dh *= (1 - h**2)

            dW1 = np.outer(state, dh)
            db1 = dh

            self.W2 += lr * dW2
            self.b2 += lr * db2
            self.W1 += lr * dW1
            self.b1 += lr * db1

        self.memory = []

# =========================
# Game Session Management (UNCHANGED)
# =========================

active_games: Dict[str, Dict] = {}
global_net = PolicyNet()
game_stats = {"ai_wins": 0, "human_wins": 0, "draws": 0, "total_games": 0}

# =========================
# API Models (UNCHANGED)
# =========================

class GameState(BaseModel):
    session_id: str
    board: List[int]
    game_over: bool
    winner: Optional[int] = None
    winning_line: Optional[List[int]] = None
    ai_confidence: Optional[float] = None
    message: Optional[str] = None

class MoveRequest(BaseModel):
    session_id: str
    position: int

class StatsResponse(BaseModel):
    ai_wins: int
    human_wins: int
    draws: int
    total_games: int
    ai_win_rate: float

# =========================
# Endpoints (UNCHANGED)
# =========================

@router.get("/test")
async def test():
    """Test endpoint"""
    return {"status": "ML API is working!", "active_games": len(active_games)}

@router.post("/tictactoe/new")
async def new_game(session_id: str):
    """Start a new Tic-Tac-Toe game"""
    print(f"[ML] Starting new game for session: {session_id}")
    
    active_games[session_id] = {
        "board": [0] * 9,
        "game_over": False
    }
    
    return {
        "session_id": session_id,
        "board": [0] * 9,
        "game_over": False,
        "winner": None,
        "winning_line": None,
        "ai_confidence": None,
        "message": "New game started. You are O, AI is X."
    }

@router.post("/tictactoe/move")
async def make_move(move: MoveRequest):
    """Handle human move and get AI response"""
    try:
        print(f"[ML] Move request - Session: {move.session_id}, Position: {move.position}")
        
        if move.session_id not in active_games:
            print(f"[ML] Game not found. Active games: {list(active_games.keys())}")
            raise HTTPException(status_code=404, detail=f"Game not found. Please start a new game.")
        
        game = active_games[move.session_id]
        board = game["board"]
        
        # Validate human move
        if move.position < 0 or move.position > 8:
            raise HTTPException(status_code=400, detail="Invalid position")
        
        if board[move.position] != 0:
            raise HTTPException(status_code=400, detail="Position already taken")
        
        if game["game_over"]:
            raise HTTPException(status_code=400, detail="Game is over")
        
        # Human move (O = -1)
        board[move.position] = -1
        print(f"[ML] Human played at {move.position}")
        
        # Check if human won
        win = winner(board)
        if win == -1:
            game["game_over"] = True
            game_stats["human_wins"] += 1
            game_stats["total_games"] += 1
            
            winning_line = None
            for a, b, c in WIN_LINES:
                if board[a] == board[b] == board[c] == -1:
                    winning_line = [a, b, c]
                    break
            
            global_net.learn(-1)
            print(f"[ML] Human wins!")
            
            return {
                "session_id": move.session_id,
                "board": board,
                "game_over": True,
                "winner": -1,
                "winning_line": winning_line,
                "ai_confidence": None,
                "message": "You win!"
            }
        
        # Check for draw
        if check_draw(board):
            game["game_over"] = True
            game_stats["draws"] += 1
            game_stats["total_games"] += 1
            global_net.learn(0)
            print(f"[ML] Draw!")
            
            return {
                "session_id": move.session_id,
                "board": board,
                "game_over": True,
                "winner": 0,
                "winning_line": None,
                "ai_confidence": None,
                "message": "Draw!"
            }
        
        # AI move (X = 1)
        ai_move, confidence = global_net.choose_move(board)
        board[ai_move] = 1
        print(f"[ML] AI played at {ai_move} (confidence: {confidence:.2f})")
        
        # Check if AI won
        win = winner(board)
        if win == 1:
            game["game_over"] = True
            game_stats["ai_wins"] += 1
            game_stats["total_games"] += 1
            
            winning_line = None
            for a, b, c in WIN_LINES:
                if board[a] == board[b] == board[c] == 1:
                    winning_line = [a, b, c]
                    break
            
            global_net.learn(1)
            print(f"[ML] AI wins!")
            
            return {
                "session_id": move.session_id,
                "board": board,
                "game_over": True,
                "winner": 1,
                "winning_line": winning_line,
                "ai_confidence": float(confidence),
                "message": "AI wins!"
            }
        
        # Check for draw after AI move
        if check_draw(board):
            game["game_over"] = True
            game_stats["draws"] += 1
            game_stats["total_games"] += 1
            global_net.learn(0)
            print(f"[ML] Draw after AI move!")
            
            return {
                "session_id": move.session_id,
                "board": board,
                "game_over": True,
                "winner": 0,
                "winning_line": None,
                "ai_confidence": None,
                "message": "Draw!"
            }
        
        # Game continues
        return {
            "session_id": move.session_id,
            "board": board,
            "game_over": False,
            "winner": None,
            "winning_line": None,
            "ai_confidence": float(confidence),
            "message": "Your turn"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ML] Error in make_move: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tictactoe/stats")
async def get_stats():
    """Get game statistics"""
    total = game_stats["total_games"]
    win_rate = (game_stats["ai_wins"] / total * 100) if total > 0 else 0.0
    
    return {
        "ai_wins": game_stats["ai_wins"],
        "human_wins": game_stats["human_wins"],
        "draws": game_stats["draws"],
        "total_games": total,
        "ai_win_rate": win_rate
    }

@router.post("/tictactoe/reset-stats")
async def reset_stats():
    """Reset statistics"""
    game_stats["ai_wins"] = 0
    game_stats["human_wins"] = 0
    game_stats["draws"] = 0
    game_stats["total_games"] = 0
    return {"status": "ok"}

# =========================
# CCXT Crypto Predictor (UNCHANGED)
# =========================

import ccxt
from collections import deque

class CryptoPredictor:
    def __init__(self):
        self.Wxh = np.random.randn(4, 16) * 0.1
        self.Whh = np.random.randn(16, 16) * 0.1
        self.Why = np.random.randn(16) * 0.1
        self.bh = np.zeros(16)
        self.by = 0.0
        self.results = deque(maxlen=200)
        self.predictions = []
        
    def normalize(self, candles):
        X = []
        for row in candles:
            o, h, l, c, v = row[1], row[2], row[3], row[4], row[5]
            X.append([
                (c - o) / o if o != 0 else 0,
                (h - o) / o if o != 0 else 0,
                (l - o) / o if o != 0 else 0,
                v / 1000000
            ])
        return np.array(X)
    
    def forward(self, inputs):
        h = np.zeros(len(self.bh))
        self.cache = []
        for x in inputs:
            h = np.tanh(x @ self.Wxh + h @ self.Whh + self.bh)
            self.cache.append((x.copy(), h.copy()))
        
        y = h @ self.Why + self.by
        return 1 / (1 + np.exp(-y))
    
    def backward(self, target, output, lr=0.01):
        dy = output - target
        
        # output layer
        self.Why -= lr * dy * self.cache[-1][1]
        self.by -= lr * dy
        
        # backprop through time
        dh = dy * self.Why
        for x, h in reversed(self.cache):
            dh_raw = dh * (1 - h**2)
            self.bh -= lr * dh_raw
            self.Wxh -= lr * np.outer(x, dh_raw)
            self.Whh -= lr * np.outer(h, dh_raw)
            dh = dh_raw @ self.Whh.T

# Global predictor instance
crypto_predictor = CryptoPredictor()

class CryptoRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    limit: int = 300

@router.post("/crypto/train-step")
async def train_step(request: CryptoRequest):
    """Perform one training step"""
    try:
        print(f"[Crypto] Training step for {request.symbol} {request.timeframe}")
        
        exchange = ccxt.binance()
        candles = np.array(exchange.fetch_ohlcv(
            request.symbol, 
            timeframe=request.timeframe, 
            limit=request.limit
        ))
        
        features = crypto_predictor.normalize(candles)
        
        window = 20
        results = []
        
        for i in range(window, len(features) - 1):
            seq = features[i-window:i]
            
            # Prediction
            prob = crypto_predictor.forward(seq)
            prediction = 1 if prob > 0.5 else 0
            
            # Ground truth
            curr_close = float(candles[i][4])
            next_close = float(candles[i+1][4])
            actual = 1 if next_close > curr_close else 0
            
            correct = int(prediction == actual)
            crypto_predictor.results.append(correct)
            
            # Learning
            crypto_predictor.backward(actual, prob)
            
            results.append({
                "prediction": int(prediction),
                "probability": float(prob),
                "actual": int(actual),
                "correct": bool(correct),
                "price": curr_close
            })
        
        accuracy = np.mean(list(crypto_predictor.results)) * 100 if crypto_predictor.results else 0
        
        print(f"[Crypto] Completed. Accuracy: {accuracy:.1f}%")
        
        return {
            "results": results[-10:],
            "accuracy": float(accuracy),
            "total_predictions": len(crypto_predictor.results)
        }
        
    except Exception as e:
        print(f"[Crypto] Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crypto/stats")
async def crypto_stats():
    """Get crypto predictor stats"""
    accuracy = np.mean(list(crypto_predictor.results)) * 100 if crypto_predictor.results else 0
    
    return {
        "accuracy": float(accuracy),
        "total_predictions": len(crypto_predictor.results)
    }

# =========================
# NEW: General Neural Network Builder
# =========================

class ActivationFunction:
    @staticmethod
    def relu(x):
        return np.maximum(0, x)
    
    @staticmethod
    def relu_derivative(x):
        return (x > 0).astype(float)
    
    @staticmethod
    def sigmoid(x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    @staticmethod
    def sigmoid_derivative(x):
        s = ActivationFunction.sigmoid(x)
        return s * (1 - s)
    
    @staticmethod
    def tanh(x):
        return np.tanh(x)
    
    @staticmethod
    def tanh_derivative(x):
        return 1 - np.tanh(x)**2
    
    @staticmethod
    def linear(x):
        return x
    
    @staticmethod
    def linear_derivative(x):
        return np.ones_like(x)
    
    @staticmethod
    def softmax(x):
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

class LossFunction:
    @staticmethod
    def mse(y_true, y_pred):
        return np.mean((y_true - y_pred)**2)
    
    @staticmethod
    def mse_derivative(y_true, y_pred):
        return 2 * (y_pred - y_true) / y_true.size
    
    @staticmethod
    def cross_entropy(y_true, y_pred):
        y_pred = np.clip(y_pred, 1e-10, 1 - 1e-10)
        return -np.mean(y_true * np.log(y_pred))
    
    @staticmethod
    def cross_entropy_derivative(y_true, y_pred):
        y_pred = np.clip(y_pred, 1e-10, 1 - 1e-10)
        return -(y_true / y_pred) / y_true.shape[0]

class Layer:
    def __init__(self, input_size, output_size, activation='relu'):
        self.W = np.random.randn(input_size, output_size) * np.sqrt(2.0 / input_size)
        self.b = np.zeros(output_size)
        self.activation = activation
        self.input = None
        self.z = None
        self.output = None
        
    def forward(self, x):
        self.input = x
        self.z = x @ self.W + self.b
        
        if self.activation == 'relu':
            self.output = ActivationFunction.relu(self.z)
        elif self.activation == 'sigmoid':
            self.output = ActivationFunction.sigmoid(self.z)
        elif self.activation == 'tanh':
            self.output = ActivationFunction.tanh(self.z)
        elif self.activation == 'linear':
            self.output = ActivationFunction.linear(self.z)
        elif self.activation == 'softmax':
            self.output = ActivationFunction.softmax(self.z)
        
        return self.output
    
    def backward(self, grad_output, learning_rate):
        # Compute gradient w.r.t. activation
        if self.activation == 'relu':
            grad_z = grad_output * ActivationFunction.relu_derivative(self.z)
        elif self.activation == 'sigmoid':
            grad_z = grad_output * ActivationFunction.sigmoid_derivative(self.z)
        elif self.activation == 'tanh':
            grad_z = grad_output * ActivationFunction.tanh_derivative(self.z)
        elif self.activation == 'linear':
            grad_z = grad_output
        elif self.activation == 'softmax':
            # For softmax with cross-entropy, grad is already computed
            grad_z = grad_output
        
        # Compute gradients
        grad_W = self.input.T @ grad_z
        grad_b = np.sum(grad_z, axis=0)
        grad_input = grad_z @ self.W.T
        
        # Update parameters
        self.W -= learning_rate * grad_W
        self.b -= learning_rate * grad_b
        
        return grad_input

class ConfigurableNetwork:
    def __init__(self, config):
        self.config = config
        self.layers = []
        self.loss_fn = config.get('loss', 'mse')
        self.learning_rate = config.get('learning_rate', 0.01)
        self.training_history = []
        
        # Build layers
        layer_configs = config.get('layers', [])
        for i, layer_config in enumerate(layer_configs):
            if i == 0:
                input_size = layer_config['input_size']
            else:
                input_size = layer_configs[i-1]['neurons']
            
            output_size = layer_config['neurons']
            activation = layer_config.get('activation', 'relu')
            
            self.layers.append(Layer(input_size, output_size, activation))
    
    def forward(self, x):
        for layer in self.layers:
            x = layer.forward(x)
        return x
    
    def backward(self, y_true, y_pred):
        # Compute loss gradient
        if self.loss_fn == 'mse':
            grad = LossFunction.mse_derivative(y_true, y_pred)
        elif self.loss_fn == 'cross_entropy':
            grad = LossFunction.cross_entropy_derivative(y_true, y_pred)
        
        # Backpropagate through layers
        for layer in reversed(self.layers):
            grad = layer.backward(grad, self.learning_rate)
    
    def train_batch(self, X, y):
        # Forward pass
        y_pred = self.forward(X)
        
        # Compute loss
        if self.loss_fn == 'mse':
            loss = LossFunction.mse(y, y_pred)
        elif self.loss_fn == 'cross_entropy':
            loss = LossFunction.cross_entropy(y, y_pred)
        
        # Backward pass
        self.backward(y, y_pred)
        
        # Compute accuracy (for classification)
        if self.config.get('task') == 'classification':
            predictions = np.argmax(y_pred, axis=1)
            targets = np.argmax(y, axis=1)
            accuracy = np.mean(predictions == targets)
        else:
            accuracy = 0.0
        
        return float(loss), float(accuracy)
    
    def predict(self, X):
        return self.forward(X)
    
    def get_weights(self):
        weights = []
        for i, layer in enumerate(self.layers):
            weights.append({
                'layer': i,
                'W': layer.W.tolist(),
                'b': layer.b.tolist()
            })
        return weights
    
    def set_weights(self, weights):
        for i, layer_weights in enumerate(weights):
            self.layers[i].W = np.array(layer_weights['W'])
            self.layers[i].b = np.array(layer_weights['b'])

# Storage for networks and datasets
active_networks: Dict[str, ConfigurableNetwork] = {}
datasets: Dict[str, Dict[str, Any]] = {}

# Built-in datasets
def generate_xor_dataset():
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    y = np.array([[0], [1], [1], [0]], dtype=float)
    return X, y

def generate_circle_dataset(n=200):
    np.random.seed(42)
    r1 = np.random.randn(n // 2) * 0.2 + 0.5
    theta1 = np.random.rand(n // 2) * 2 * np.pi
    x1 = r1 * np.cos(theta1)
    y1 = r1 * np.sin(theta1)
    
    r2 = np.random.randn(n // 2) * 0.2 + 1.5
    theta2 = np.random.rand(n // 2) * 2 * np.pi
    x2 = r2 * np.cos(theta2)
    y2 = r2 * np.sin(theta2)
    
    X = np.vstack([np.column_stack([x1, y1]), np.column_stack([x2, y2])])
    y = np.vstack([np.zeros((n // 2, 1)), np.ones((n // 2, 1))])
    
    # Shuffle
    indices = np.random.permutation(n)
    return X[indices], y[indices]

def generate_spiral_dataset(n=200):
    np.random.seed(42)
    n_per_class = n // 2
    
    theta1 = np.linspace(0, 4 * np.pi, n_per_class) + np.random.randn(n_per_class) * 0.2
    r1 = np.linspace(0.5, 2, n_per_class) + np.random.randn(n_per_class) * 0.1
    x1 = r1 * np.cos(theta1)
    y1 = r1 * np.sin(theta1)
    
    theta2 = np.linspace(0, 4 * np.pi, n_per_class) + np.random.randn(n_per_class) * 0.2 + np.pi
    r2 = np.linspace(0.5, 2, n_per_class) + np.random.randn(n_per_class) * 0.1
    x2 = r2 * np.cos(theta2)
    y2 = r2 * np.sin(theta2)
    
    X = np.vstack([np.column_stack([x1, y1]), np.column_stack([x2, y2])])
    y = np.vstack([np.zeros((n_per_class, 1)), np.ones((n_per_class, 1))])
    
    indices = np.random.permutation(n)
    return X[indices], y[indices]

def generate_iris_dataset():
    # Simplified Iris dataset (first 2 features, 2 classes)
    np.random.seed(42)
    
    # Setosa (class 0)
    setosa = np.random.randn(50, 2) * 0.3 + np.array([5.0, 3.4])
    
    # Versicolor (class 1)
    versicolor = np.random.randn(50, 2) * 0.4 + np.array([6.5, 2.8])
    
    X = np.vstack([setosa, versicolor])
    y = np.vstack([np.zeros((50, 1)), np.ones((50, 1))])
    
    indices = np.random.permutation(100)
    return X[indices], y[indices]

# Initialize built-in datasets
X_xor, y_xor = generate_xor_dataset()
datasets['xor'] = {'X': X_xor, 'y': y_xor, 'name': 'XOR Problem', 'type': 'classification'}

X_circles, y_circles = generate_circle_dataset()
datasets['circles'] = {'X': X_circles, 'y': y_circles, 'name': 'Concentric Circles', 'type': 'classification'}

X_spiral, y_spiral = generate_spiral_dataset()
datasets['spiral'] = {'X': X_spiral, 'y': y_spiral, 'name': 'Spiral', 'type': 'classification'}

X_iris, y_iris = generate_iris_dataset()
datasets['iris'] = {'X': X_iris, 'y': y_iris, 'name': 'Iris (Simplified)', 'type': 'classification'}

# =========================
# Network Builder API Models
# =========================

class LayerConfig(BaseModel):
    neurons: int
    activation: str = 'relu'
    input_size: Optional[int] = None

class NetworkConfig(BaseModel):
    name: str
    layers: List[LayerConfig]
    loss: str = 'mse'
    learning_rate: float = 0.01
    task: str = 'classification'  # or 'regression'

class TrainRequest(BaseModel):
    network_id: str
    dataset_id: str
    epochs: int = 100
    batch_size: int = 32

# =========================
# Network Builder Endpoints
# =========================

@router.post("/network/create")
async def create_network(config: NetworkConfig):
    """Create a new configurable neural network"""
    try:
        print(f"[Network] Creating network: {config.name}")
        
        network_id = f"net-{datetime.now().timestamp()}"
        
        # Convert Pydantic models to dict
        config_dict = {
            'name': config.name,
            'layers': [layer.dict() for layer in config.layers],
            'loss': config.loss,
            'learning_rate': config.learning_rate,
            'task': config.task
        }
        
        network = ConfigurableNetwork(config_dict)
        active_networks[network_id] = network
        
        print(f"[Network] Created network {network_id} with {len(config.layers)} layers")
        
        return {
            "network_id": network_id,
            "config": config_dict,
            "status": "created"
        }
        
    except Exception as e:
        print(f"[Network] Error creating network: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/network/list")
async def list_networks():
    """List all active networks"""
    return {
        "networks": [
            {
                "id": net_id,
                "name": net.config.get('name', 'Unnamed'),
                "layers": len(net.layers),
                "training_history": len(net.training_history)
            }
            for net_id, net in active_networks.items()
        ]
    }

@router.delete("/network/{network_id}")
async def delete_network(network_id: str):
    """Delete a network"""
    if network_id in active_networks:
        del active_networks[network_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Network not found")

@router.post("/network/train")
async def train_network(request: TrainRequest):
    """Train a network on a dataset"""
    try:
        if request.network_id not in active_networks:
            raise HTTPException(status_code=404, detail="Network not found")
        
        if request.dataset_id not in datasets:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        network = active_networks[request.network_id]
        dataset = datasets[request.dataset_id]
        
        X = dataset['X']
        y = dataset['y']
        
        # Convert y to one-hot for classification
        if network.config.get('task') == 'classification' and y.shape[1] == 1:
            n_classes = len(np.unique(y))
            y_onehot = np.zeros((y.shape[0], n_classes))
            y_onehot[np.arange(y.shape[0]), y.astype(int).flatten()] = 1
            y = y_onehot
        
        print(f"[Network] Training {request.network_id} on {request.dataset_id}")
        print(f"[Network] X shape: {X.shape}, y shape: {y.shape}")
        
        training_log = []
        n_samples = X.shape[0]
        
        for epoch in range(request.epochs):
            # Shuffle data
            indices = np.random.permutation(n_samples)
            X_shuffled = X[indices]
            y_shuffled = y[indices]
            
            epoch_losses = []
            epoch_accuracies = []
            
            # Mini-batch training
            for i in range(0, n_samples, request.batch_size):
                batch_X = X_shuffled[i:i + request.batch_size]
                batch_y = y_shuffled[i:i + request.batch_size]
                
                loss, accuracy = network.train_batch(batch_X, batch_y)
                epoch_losses.append(loss)
                epoch_accuracies.append(accuracy)
            
            avg_loss = np.mean(epoch_losses)
            avg_accuracy = np.mean(epoch_accuracies)
            
            # Log every 10 epochs or last epoch
            if (epoch + 1) % 10 == 0 or epoch == request.epochs - 1:
                log_entry = {
                    "epoch": epoch + 1,
                    "loss": float(avg_loss),
                    "accuracy": float(avg_accuracy)
                }
                training_log.append(log_entry)
                network.training_history.append(log_entry)
                print(f"[Network] Epoch {epoch + 1}/{request.epochs} - Loss: {avg_loss:.4f}, Acc: {avg_accuracy:.4f}")
        
        return {
            "status": "completed",
            "epochs_trained": request.epochs,
            "final_loss": float(avg_loss),
            "final_accuracy": float(avg_accuracy),
            "training_log": training_log
        }
        
    except Exception as e:
        print(f"[Network] Training error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/network/predict")
async def network_predict(network_id: str, data: List[List[float]]):
    """Make predictions with a network"""
    try:
        if network_id not in active_networks:
            raise HTTPException(status_code=404, detail="Network not found")
        
        network = active_networks[network_id]
        X = np.array(data)
        
        predictions = network.predict(X)
        
        return {
            "predictions": predictions.tolist(),
            "shape": predictions.shape
        }
        
    except Exception as e:
        print(f"[Network] Prediction error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/network/{network_id}/history")
async def get_training_history(network_id: str):
    """Get training history for a network"""
    if network_id not in active_networks:
        raise HTTPException(status_code=404, detail="Network not found")
    
    network = active_networks[network_id]
    return {
        "history": network.training_history
    }

@router.get("/network/{network_id}/weights")
async def get_network_weights(network_id: str):
    """Get network weights"""
    if network_id not in active_networks:
        raise HTTPException(status_code=404, detail="Network not found")
    
    network = active_networks[network_id]
    return {
        "weights": network.get_weights()
    }

@router.get("/datasets/list")
async def list_datasets():
    """List available datasets"""
    return {
        "datasets": [
            {
                "id": ds_id,
                "name": ds_info.get('name', ds_id),
                "type": ds_info.get('type', 'unknown'),
                "samples": ds_info['X'].shape[0] if 'X' in ds_info else 0,
                "features": ds_info['X'].shape[1] if 'X' in ds_info else 0
            }
            for ds_id, ds_info in datasets.items()
        ]
    }

@router.get("/datasets/{dataset_id}/sample")
async def get_dataset_sample(dataset_id: str, n: int = 100):
    """Get a sample of dataset points for visualization"""
    if dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset = datasets[dataset_id]
    X = dataset['X']
    y = dataset['y']
    
    # Get a sample
    n_samples = min(n, X.shape[0])
    indices = np.random.choice(X.shape[0], n_samples, replace=False)
    
    return {
        "X": X[indices].tolist(),
        "y": y[indices].tolist(),
        "total_samples": X.shape[0]
    }

print("[ML Backend] Loaded successfully with Network Builder")