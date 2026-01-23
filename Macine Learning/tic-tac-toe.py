import numpy as np

# =========================
# Game Utilities
# =========================

WIN_LINES = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def winner(board):
    for a,b,c in WIN_LINES:
        if board[a] == board[b] == board[c] != 0:
            return board[a]
    return 0

def print_board(board):
    s = {1:'X', -1:'O', 0:'.'}
    for i in range(0,9,3):
        print(" ".join(s[x] for x in board[i:i+3]))
    print()

# =========================
# Neural Network (Policy)
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

        self.memory = []  # (state, action_probs, action)

    def forward(self, x):
        h = np.tanh(x @ self.W1 + self.b1)
        logits = h @ self.W2 + self.b2
        return softmax(logits), h

    def choose_move(self, board):
        probs, h = self.forward(board)
        probs = probs * (board == 0)  # mask illegal moves
        probs = probs / np.sum(probs)

        action = np.random.choice(9, p=probs)
        self.memory.append((board.copy(), probs, action, h))
        return action

    def learn(self, reward, lr=0.05):
        for state, probs, action, h in self.memory:
            dlog = -probs
            dlog[action] += 1
            dlog *= reward

            # backprop
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
# Human vs NN
# =========================

def play():
    net = PolicyNet()

    while True:
        board = np.zeros(9)
        print("\nNew Game! You are O. NN is X.\n")

        while True:
            # NN move
            move = net.choose_move(board)
            board[move] = 1
            print_board(board)

            if winner(board) == 1:
                print("NN wins!")
                net.learn(+1)
                break

            if 0 not in board:
                print("Draw.")
                net.learn(0)
                break

            # Human move
            move = int(input("Your move (0-8): "))
            if board[move] != 0:
                print("Illegal move!")
                continue
            board[move] = -1
            print_board(board)

            if winner(board) == -1:
                print("You win!")
                net.learn(-1)
                break

        if input("Play again? (y/n): ").lower() != "y":
            break

# =========================
# Run
# =========================

if __name__ == "__main__":
    play()
