import ccxt
import numpy as np
import time
from collections import deque

# ==========================
# CCXT: Fetch OHLCV
# ==========================

exchange = ccxt.binance()
symbol = 'BTC/USDT'
timeframe = '1m'
limit = 300

def fetch_ohlcv():
    return np.array(exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit))

# ==========================
# Feature Engineering
# ==========================

def normalize(candles):
    X = []
    for o,h,l,c,v in candles:
        X.append([
            (c - o) / o,
            (h - o) / o,
            (l - o) / o,
            v
        ])
    return np.array(X)

# ==========================
# Trask-Style Vanilla RNN
# ==========================
class RNN:
    def __init__(self, input_size, hidden_size):
        self.Wxh = np.random.randn(input_size, hidden_size) * 0.1
        self.Whh = np.random.randn(hidden_size, hidden_size) * 0.1
        self.Why = np.random.randn(hidden_size) * 0.1  # <- vector
        self.bh = np.zeros(hidden_size)
        self.by = 0.0  # <- scalar

    def forward(self, inputs):
        h = np.zeros(len(self.bh))
        self.cache = []
        for x in inputs:
            h = np.tanh(x @ self.Wxh + h @ self.Whh + self.bh)
            self.cache.append((x, h))

        y = h @ self.Why + self.by
        return 1 / (1 + np.exp(-y))  # scalar

    def backward(self, target, output, lr=0.01):
        dy = output - target  # scalar

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


# ==========================
# Online Training + Accuracy
# ==========================

np.random.seed(0)
rnn = RNN(input_size=4, hidden_size=16)
window = 20

results = deque(maxlen=200)  # rolling accuracy window

print("\nStarting online learning with accuracy tracking\n")

while True:
    candles = fetch_ohlcv()
    features = normalize(candles[:,1:])  # drop timestamp

    for i in range(window, len(features)-1):
        seq = features[i-window:i]

        # ---- Prediction ----
        prob = rnn.forward(seq)  # <- scalar, no [0]
        prediction = 1 if prob > 0.5 else 0

        # ---- Ground truth ----
        curr_close = candles[i][4]
        next_close = candles[i+1][4]
        actual = 1 if next_close > curr_close else 0

        correct = int(prediction == actual)
        results.append(correct)

        # ---- Learning ----
        rnn.backward(actual, prob)


    accuracy = np.mean(results) * 100 if results else 0

    print(
        f"Pred={prediction} "
        f"Prob={prob:.3f} "
        f"Actual={actual} "
        f"Correct={correct} "
        f"Rolling Acc={accuracy:.2f}%"
    )

    time.sleep(60)