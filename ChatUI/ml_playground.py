# streamlit_ml_game_playground_integrated.py
"""
Integrated Streamlit ML Game Playground
- Example datasets (Iris, Digits, Moons, California Housing, MNIST via fetch_openml)
- MLP + ConvNet builders
- Visual NN diagrams (Graphviz)
- Tic-Tac-Toe GUI with suggested move highlighting
- Play vs AI (Minimax / Random / Trained NN / Q-agent)
- Q-learning RL training (tabular)
- Save / Load models (architect config + state_dict)
- Metrics: loss curve, confusion matrix, ROC for binary
"""

import streamlit as st
st.set_page_config(page_title="ML Game Playground (Integrated)", layout="wide")
import numpy as np
import pandas as pd
import torch, torch.nn as nn, torch.optim as optim
from sklearn.datasets import load_iris, load_digits, make_moons, fetch_california_housing, fetch_openml
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, confusion_matrix, roc_curve, auc, mean_squared_error
import matplotlib.pyplot as plt
import io, base64, json, time, os

# Try to import torchvision for CIFAR; if not present hide CIFAR option
try:
    import torchvision
    from torchvision import transforms, datasets
    HAVE_TORCHVISION = True
except Exception:
    HAVE_TORCHVISION = False

# ---------------------------
# Utilities & Session Init
# ---------------------------
def init_session():
    s = st.session_state
    if 'ttt_board' not in s: s.ttt_board = [0]*9
    if 'ttt_turn' not in s: s.ttt_turn = 1
    if 'last_model' not in s: s.last_model = None
    if 'last_model_meta' not in s: s.last_model_meta = None
    if 'rl_q' not in s: s.rl_q = {}
    if 'datasets' not in s: s.datasets = {}
    if 'training_history' not in s: s.training_history = {}
init_session()

WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

def check_winner(board):
    for a,b,c in WIN_LINES:
        if board[a] != 0 and board[a]==board[b]==board[c]:
            return board[a]
    if all(x!=0 for x in board):
        return 0
    return None

def board_to_input(board, perspective=1):
    # returns length-9 vector in {-1,0,1} where perspective==1 maps X->1 else O->1
    arr = np.array(board)
    if perspective==1:
        return np.where(arr==0,0, np.where(arr==1,1,-1)).astype(np.float32)
    else:
        return np.where(arr==0,0, np.where(arr==2,1,-1)).astype(np.float32)

def minimax_move(board, player):
    # simple minimax (reasonable for 3x3)
    opponent = 3-player
    def s(b):
        w = check_winner(b)
        if w==player: return 1
        if w==opponent: return -1
        return 0
    def mm(b, turn):
        w = check_winner(b)
        if w is not None: return s(b), None
        best=-999; best_move=None
        for i in range(9):
            if b[i]==0:
                b[i]=turn
                val,_ = mm(b, 3-turn)
                b[i]=0
                val = -val
                if val>best:
                    best=val; best_move=i
        return best, best_move
    _, mv = mm(board[:], player)
    if mv is None:
        empties = [i for i,v in enumerate(board) if v==0]
        return np.random.choice(empties)
    return mv

# ---------------------------
# Model Classes
# ---------------------------
class MLP(nn.Module):
    def __init__(self, input_size, output_size, hidden_layers=[64,32], activation='ReLU', dropout=0.0):
        super().__init__()
        act_map = {'ReLU':nn.ReLU(),'Tanh':nn.Tanh(),'Sigmoid':nn.Sigmoid(),'LeakyReLU':nn.LeakyReLU()}
        act = act_map.get(activation, nn.ReLU())
        layers=[]
        last=input_size
        for h in hidden_layers:
            layers.append(nn.Linear(last,h)); layers.append(act)
            if dropout>0: layers.append(nn.Dropout(dropout))
            last=h
        layers.append(nn.Linear(last, output_size))
        self.net = nn.Sequential(*layers)
    def forward(self,x): return self.net(x)

class ConvNetSmall(nn.Module):
    def __init__(self, in_ch=1, num_classes=10, conv_channels=[16,32], fc=[64], activation='ReLU'):
        super().__init__()
        act_map = {'ReLU':nn.ReLU(),'Tanh':nn.Tanh(),'Sigmoid':nn.Sigmoid(),'LeakyReLU':nn.LeakyReLU()}
        act = act_map.get(activation, nn.ReLU())
        convs=[]
        last=in_ch
        for ch in conv_channels:
            convs += [nn.Conv2d(last,ch,3,padding=1), act, nn.MaxPool2d(2)]
            last=ch
        self.conv = nn.Sequential(*convs)
        self.pool = nn.AdaptiveAvgPool2d(1)
        fc_layers=[]
        last_fc = last
        for f in fc:
            fc_layers += [nn.Linear(last_fc,f), act]
            last_fc = f
        fc_layers += [nn.Linear(last_fc, num_classes)]
        self.fc = nn.Sequential(*fc_layers)
    def forward(self,x):
        x = self.conv(x)
        x = self.pool(x).view(x.size(0), -1)
        return self.fc(x)

# ---------------------------
# Diagram helpers (Graphviz)
# ---------------------------
def draw_feedforward_diagram(input_size, hidden_layers, output_size):
    dot = "digraph G { rankdir=LR; node [shape=record];\n"
    dot += f'input [label="Input\\n{input_size}"];\n'
    for i,h in enumerate(hidden_layers):
        dot += f'h{i} [label="Hidden {i+1}\\n{h}"];\n'
    dot += f'out [label="Output\\n{output_size}"];\n'
    # edges
    dot += "input -> h0;\n"
    for i in range(len(hidden_layers)-1):
        dot += f'h{i} -> h{i+1};\n'
    dot += f'h{len(hidden_layers)-1} -> out;\n'
    dot += "}"
    return dot

def draw_conv_diagram(in_shape, conv_channels, fc):
    # simple textual diagram in DOT
    h,w = in_shape
    dot = "digraph G { rankdir=LR; node [shape=record];\n"
    dot += f'input [label="Input\\n1x{h}x{w}"];\n'
    for i,ch in enumerate(conv_channels):
        dot += f'c{i} [label="Conv {i+1}\\n{ch} filters"];\n'
        dot += f'p{i} [label="Pool {i+1}"];\n    '
    dot += 'fc [label="FC\\n' + ','.join(str(x) for x in fc) + '"];\n'
    dot += "input -> c0 -> p0"
    for i in range(1,len(conv_channels)):
        dot += f" -> c{i} -> p{i}"
    dot += " -> fc;\n}\n"
    return dot

# ---------------------------
# Sidebar: Global options
# ---------------------------
st.sidebar.header("Global")
seed = st.sidebar.number_input("Random seed", value=42)
np.random.seed(seed); torch.manual_seed(seed)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
st.sidebar.write("Device:", device)

# ---------------------------
# Main layout: tabs
# ---------------------------
tabs = st.tabs(["Datasets", "Model & Train", "Metrics", "Tic-Tac-Toe GUI", "RL (Q-learning)", "Save/Load & Export", "Diagrams & Examples"])

# ---------- Tab: Datasets ----------
with tabs[0]:
    st.header("Datasets & Example loaders")
    st.markdown("Choose an example dataset or upload your CSV. For images use Digits / MNIST / CIFAR.")
    ds = st.selectbox("Dataset", ["Iris (classification)", "Digits (classification)", "Moons (toy)", "California Housing (regression)", "MNIST (fetch_openml)"] + (["CIFAR-10 (torchvision)"] if HAVE_TORCHVISION else [] ) + ["Upload CSV"])
    if ds == "Iris (classification)":
        data = load_iris()
        X, y = data.data, data.target
        st.write("Iris preview:")
        st.dataframe(pd.DataFrame(X, columns=data.feature_names).head())
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'classification'}
    elif ds == "Digits (classification)":
        digits = load_digits()
        X, y = digits.data, digits.target
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'classification'}
        st.image([digits.images[i] for i in range(6)], width=100, caption=[str(digits.target[i]) for i in range(6)])
    elif ds == "Moons (toy)":
        X,y = make_moons(n_samples=500, noise=0.2, random_state=seed)
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'classification'}
        st.write(pd.DataFrame(np.hstack([X,y.reshape(-1,1)]), columns=['x1','x2','target']).head())
    elif ds == "California Housing (regression)":
        data = fetch_california_housing()
        X,y = data.data, data.target
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'regression'}
        st.dataframe(pd.DataFrame(X, columns=data.feature_names).head())
    elif ds == "MNIST (fetch_openml)":
        with st.spinner("Fetching MNIST (this may take ~10s depending on your network)..."):
            mn = fetch_openml('mnist_784', version=1, as_frame=False)
        X,y = mn['data'].astype(np.float32)/255.0, mn['target'].astype(int)
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'images', 'image_shape':(28,28)}
        st.write("MNIST loaded:", X.shape)
    elif ds == "CIFAR-10 (torchvision)" and HAVE_TORCHVISION:
        st.info("Loading CIFAR via torchvision; this will download if not present.")
        transform = transforms.Compose([transforms.ToTensor()])
        cifar = datasets.CIFAR10(root='./data', train=True, download=True)
        X = np.array([np.transpose(np.array(cifar[i][0]), (1,2,0)) for i in range(len(cifar))])[:2000] # keep small subset
        y = np.array([cifar[i][1] for i in range(len(cifar))])[:2000]
        st.session_state.datasets['current'] = {'X':X, 'y':y, 'task':'images', 'image_shape':(32,32,3)}
        st.write("CIFAR subset loaded (2000 samples)")
    elif ds == "Upload CSV":
        up = st.file_uploader("Upload CSV", type=['csv'])
        if up:
            df = pd.read_csv(up)
            st.session_state.datasets['current'] = {'X': df.drop(columns=[st.selectbox("Pick target column", df.columns)], errors='ignore').values, 'y': df.iloc[:, -1].values, 'task':'classification'}
            st.write("Uploaded dataset preview:")
            st.dataframe(df.head())

# ---------- Tab: Model & Train ----------
with tabs[1]:
    st.header("Model configuration & training")
    if 'current' not in st.session_state.datasets:
        st.info("Pick a dataset first in the Datasets tab.")
    else:
        D = st.session_state.datasets['current']
        X, y = D['X'], D['y']; task = D.get('task','classification')
        test_size = st.slider("Test size", 0.05, 0.5, 0.2)
        if task == 'images':
            # expect X shaped (n,h,w) or (n,h,w,c)
            if X.ndim==2:
                # flattened images (e.g., MNIST from fetch_openml)
                img_h, img_w = D.get('image_shape', (28,28))
                X_img = X.reshape(-1,img_h,img_w)
                X = X_img
            n = len(X)
            st.write(f"Image dataset with {n} samples")
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=seed)
        else:
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X)
            X_train, X_test, y_train, y_test = train_test_split(Xs, y, test_size=test_size, random_state=seed)
        st.write("Train / Test sizes:", len(X_train), len(X_test))

        model_kind = st.selectbox("Model kind", ["MLP", "ConvNet (images)", "Custom MLP (game board)"])
        if model_kind == "MLP" or model_kind=="Custom MLP (game board)":
            in_size = X_train.shape[1] if X_train.ndim==2 else X_train.reshape(len(X_train),-1).shape[1]
            st.write("Input size:", in_size)
            hidden_spec = st.text_input("Hidden layers (comma sep)", value="128,64")
            hidden_layers = [int(x.strip()) for x in hidden_spec.split(',') if x.strip()]
            activation = st.selectbox("Activation", ['ReLU','Tanh','Sigmoid','LeakyReLU'])
            dropout = st.slider("Dropout", 0.0, 0.5, 0.0)
            out_size = len(np.unique(y_train)) if task!='regression' else 1
            model = MLP(in_size, out_size, hidden_layers, activation, dropout)
        else:
            # conv net
            img_shape = X_train[0].shape
            if X_train.ndim==3: # (n,h,w) -> add channel
                in_ch = 1; img_h, img_w = X_train[0].shape
            else:
                in_ch = img_shape[2]; img_h, img_w = img_shape[0], img_shape[1]
            conv_spec = st.text_input("Conv channels (comma) e.g. 16,32", value="16,32")
            conv_channels = [int(x.strip()) for x in conv_spec.split(',') if x.strip()]
            fc_spec = st.text_input("FC layers (comma)", value="64")
            fc_layers = [int(x.strip()) for x in fc_spec.split(',') if x.strip()]
            activation = st.selectbox("Activation", ['ReLU','Tanh','Sigmoid','LeakyReLU'])
            model = ConvNetSmall(in_ch, num_classes=len(np.unique(y_train)), conv_channels=conv_channels, fc=fc_layers, activation=activation)

        # training params
        lr = st.number_input("Learning rate", value=0.001, format="%.6f")
        optimizer_choice = st.selectbox("Optimizer", ["Adam","SGD"])
        epochs = st.slider("Epochs", 1, 200, 20)
        batch_size = st.selectbox("Batch size", [16,32,64,128], index=1)

        if st.button("Train model"):
            model = model.to(device)
            # prepare tensors
            if task == 'images':
                # create tensors with channels-first
                if X_train.ndim==3: # n,h,w
                    Xtr = torch.tensor(X_train.reshape(-1,1,img_h,img_w), dtype=torch.float32).to(device)
                    Xte = torch.tensor(X_test.reshape(-1,1,img_h,img_w), dtype=torch.float32).to(device)
                else:
                    Xtr = torch.tensor(np.transpose(X_train, (0,3,1,2)), dtype=torch.float32).to(device)
                    Xte = torch.tensor(np.transpose(X_test, (0,3,1,2)), dtype=torch.float32).to(device)
                ytr = torch.tensor(y_train, dtype=torch.long).to(device)
                yte = torch.tensor(y_test, dtype=torch.long).to(device)
            else:
                Xtr = torch.tensor(X_train, dtype=torch.float32).to(device)
                Xte = torch.tensor(X_test, dtype=torch.float32).to(device)
                ytr = torch.tensor(y_train, dtype=torch.long if len(np.unique(y_train))>2 or task=='classification' else torch.float32).to(device)
                yte = torch.tensor(y_test, dtype=torch.long if len(np.unique(y_train))>2 or task=='classification' else torch.float32).to(device)

            criterion = nn.CrossEntropyLoss() if (task!='regression' and (len(np.unique(y_train))>1)) else nn.MSELoss()
            optimizer = optim.Adam(model.parameters(), lr=lr) if optimizer_choice=='Adam' else optim.SGD(model.parameters(), lr=lr)

            history = []
            for ep in range(epochs):
                model.train()
                perm = np.random.permutation(len(Xtr))
                running_loss = 0.0
                for i in range(0, len(perm), batch_size):
                    idx = perm[i:i+batch_size]
                    xb = Xtr[idx]
                    yb = ytr[idx]
                    optimizer.zero_grad()
                    out = model(xb)
                    if isinstance(criterion, nn.MSELoss):
                        loss = criterion(out.view(-1), yb.float())
                    else:
                        loss = criterion(out, yb.long())
                    loss.backward(); optimizer.step()
                    running_loss += float(loss.item())*len(idx)
                avg_loss = running_loss/len(Xtr)
                history.append(avg_loss)
                st.progress((ep+1)/epochs)
            # store trained model + metadata in session
            st.session_state.last_model = model.cpu()
            meta = {'task':task, 'kind': model_kind, 'hidden':hidden_layers if model_kind!='ConvNet (images)' else None,
                    'conv_channels': conv_channels if model_kind=='ConvNet (images)' else None,
                    'input_shape': X_train.shape, 'output_size': len(np.unique(y_train)) if task!='regression' else 1}
            st.session_state.last_model_meta = meta
            st.session_state.training_history = history
            st.success("Training complete and saved to session (`last_model`).")
            fig, ax = plt.subplots()
            ax.plot(history); ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
            st.pyplot(fig)

# ---------- Tab: Metrics ----------
with tabs[2]:
    st.header("Metrics & Visualizations")
    if st.session_state.last_model is None:
        st.info("No model in session. Train one in Model & Train tab.")
    else:
        model = st.session_state.last_model
        meta  = st.session_state.last_model_meta or {}
        st.write("Model meta:", meta)
        # quick evaluation on example dataset if present
        if 'current' in st.session_state.datasets:
            D = st.session_state.datasets['current']
            X,y = D['X'], D['y']; task = D.get('task','classification')
            if task=='images':
                # use small subset
                sample = 200
                Xs = X[:sample]
                ys = y[:sample]
                if Xs.ndim==3:
                    Xt = torch.tensor(Xs.reshape(-1,1,Xs.shape[1],Xs.shape[2]), dtype=torch.float32)
                else:
                    Xt = torch.tensor(np.transpose(Xs, (0,3,1,2)), dtype=torch.float32)
                with torch.no_grad():
                    out = model(Xt).numpy()
                    preds = np.argmax(out, axis=1)
                    cm = confusion_matrix(ys, preds)
                    st.write("Confusion matrix:")
                    fig, ax = plt.subplots()
                    ax.imshow(cm); ax.set_xlabel('Pred'); ax.set_ylabel('True')
                    st.pyplot(fig)
            else:
                scaler = StandardScaler()
                Xs = scaler.fit_transform(X)
                Xt = torch.tensor(Xs, dtype=torch.float32)
                with torch.no_grad():
                    out = model(Xt).numpy()
                    if out.ndim>1 and out.shape[1]>1:
                        preds = np.argmax(out, axis=1)
                        cm = confusion_matrix(y, preds)
                        fig, ax = plt.subplots()
                        ax.imshow(cm); st.pyplot(fig)
                        if len(np.unique(y))==2:
                            fpr,tpr,_ = roc_curve(y, out[:,1])
                            roc_auc = auc(fpr,tpr)
                            fig2, ax2 = plt.subplots()
                            ax2.plot(fpr,tpr,label=f"AUC {roc_auc:.3f}"); ax2.legend()
                            st.pyplot(fig2)
                    else:
                        mse = mean_squared_error(y, out.ravel())
                        st.write("MSE over full dataset:", mse)

# ---------- Tab: Tic-Tac-Toe GUI ----------
with tabs[3]:
    st.header("Tic-Tac-Toe — Visual board")
    colleft, colright = st.columns([3,1])
    with colright:
        opp = st.selectbox("Opponent", ["Trained model (last_model)", "Minimax", "Random", "Q-agent (if trained)"])
        you_as = st.selectbox("You play as", ["X (first)", "O (second)"])
        human = 1 if you_as.startswith('X') else 2
        if st.button("Reset board"):
            st.session_state.ttt_board = [0]*9
            st.session_state.ttt_turn = 1
    with colleft:
        board = st.session_state.ttt_board
        turn = st.session_state.ttt_turn
        # compute model suggested move (if model available)
        suggested = None
        if st.session_state.last_model is not None:
            try:
                suggested = int(np.argmax(st.session_state.last_model(torch.tensor([board_to_input(board)], dtype=torch.float32)).detach().numpy().ravel()))
                # mask illegal
                if board[suggested] != 0:
                    suggested = None
            except Exception:
                suggested = None

        # render board as 3x3 buttons, highlight suggested
        for r in range(3):
            cols = st.columns(3)
            for c in range(3):
                idx = r*3+c
                label = " "
                if board[idx]==1: label="X"
                elif board[idx]==2: label="O"
                btn_label = label
                if suggested == idx:
                    btn_label = f"{label}\\n(suggest)" if label!=" " else "(suggest)"
                if cols[c].button(btn_label, key=f"ttt_{idx}"):
                    # user click
                    if board[idx]==0 and turn==human and check_winner(board) is None:
                        board[idx]=human
                        st.session_state.ttt_turn = 3-human

        # after possible human move, check and let AI move if needed
        winner = check_winner(board)
        if winner is not None:
            if winner==0:
                st.success("Draw!")
            else:
                st.success(f"{'X' if winner==1 else 'O'} wins!")
        else:
            if st.session_state.ttt_turn != human:
                # AI move
                if opp == "Random":
                    empties=[i for i,v in enumerate(board) if v==0]; mv = np.random.choice(empties)
                elif opp == "Minimax":
                    mv = minimax_move(board, st.session_state.ttt_turn)
                elif opp == "Q-agent (if trained)":
                    q = st.session_state.rl_q
                    if q:
                        # choose best action by Q
                        state = ''.join(map(str, board))
                        empties=[i for i in range(9) if board[i]==0]
                        qvals=[q.get((state,i),0) for i in empties]
                        mv = empties[int(np.argmax(qvals))]
                    else:
                        mv = minimax_move(board, st.session_state.ttt_turn)
                else:
                    # trained model
                    if st.session_state.last_model is not None:
                        try:
                            mv = int(np.argmax(st.session_state.last_model(torch.tensor([board_to_input(board)], dtype=torch.float32)).detach().numpy().ravel()))
                            if board[mv]!=0:
                                mv = minimax_move(board, st.session_state.ttt_turn)
                        except Exception:
                            mv = minimax_move(board, st.session_state.ttt_turn)
                    else:
                        mv = minimax_move(board, st.session_state.ttt_turn)
                board[mv] = st.session_state.ttt_turn
                st.session_state.ttt_turn = 3 - st.session_state.ttt_turn
                st.experimental_rerun()

# ---------- Tab: RL (Q-learning) ----------
with tabs[4]:
    st.header("Reinforcement Learning — Tabular Q-learning for Tic-Tac-Toe")
    episodes = st.number_input("Episodes", value=2000, step=100)
    eps = st.slider("Epsilon (exploration)", 0.0, 1.0, 0.2)
    alpha = st.slider("Alpha (learning rate)", 0.01, 1.0, 0.5)
    gamma = st.slider("Gamma (discount)", 0.0, 1.0, 0.9)
    if st.button("Train Q-agent"):
        Q = {}
        pbar = st.progress(0)
        for ep in range(int(episodes)):
            board = [0]*9; current = 1; history=[]
            while True:
                state = ''.join(map(str,board))
                empties = [i for i,v in enumerate(board) if v==0]
                if np.random.rand() < eps:
                    a = np.random.choice(empties)
                else:
                    qvals = [Q.get((state,a),0) for a in empties]
                    a = empties[int(np.argmax(qvals))]
                board[a] = current
                history.append((state,a,current))
                w = check_winner(board)
                if w is not None:
                    for (s,a,p) in history:
                        if w==0: r=0.5
                        elif w==p: r=1.0
                        else: r=-1.0
                        old = Q.get((s,a),0)
                        Q[(s,a)] = old + alpha * (r - old)
                    break
                current = 3-current
            if ep % max(1,int(episodes/100))==0:
                pbar.progress(int(ep/episodes*100))
        st.session_state.rl_q = Q
        st.success("Q-agent trained and stored in session.")

    if st.button("Show Q-size"):
        st.write("Q table size:", len(st.session_state.rl_q))

# ---------- Tab: Save/Load & Export ----------
with tabs[5]:
    st.header("Save / Load model checkpoints")
    st.write("Checkpoints include a JSON meta describing architecture + the PyTorch state_dict inside a .pt file (single dict).")
    if st.session_state.last_model is not None:
        if st.button("Download last model checkpoint"):
            meta = st.session_state.last_model_meta or {}
            ckpt = {'meta': meta, 'state_dict': st.session_state.last_model.state_dict()}
            buf = io.BytesIO(); torch.save(ckpt, buf); buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            href = f"data:application/octet-stream;base64,{b64}"
            st.markdown(f"[Download checkpoint]({href})")
    up = st.file_uploader("Upload checkpoint (.pt)", type=['pt','pth'])
    if up:
        ckpt = torch.load(up, map_location='cpu')
        meta = ckpt.get('meta')
        sd = ckpt.get('state_dict')
        if meta is None or sd is None:
            st.error("This file does not look like a checkpoint produced by this app (missing meta/state_dict).")
        else:
            # Try to recreate architecture from meta
            kind = meta.get('kind','MLP')
            try:
                if kind.startswith('ConvNet'):
                    # build small conv to accept
                    model = ConvNetSmall(in_ch=1, num_classes=meta.get('output_size',10), conv_channels=meta.get('conv_channels',[16,32]), fc=meta.get('fc',[64]))
                else:
                    model = MLP(input_size=meta.get('input_shape', (1,))[1] if meta.get('input_shape') is not None else 9,
                                output_size=meta.get('output_size', 10),
                                hidden_layers=meta.get('hidden',[64,32]))
                model.load_state_dict(sd)
                st.session_state.last_model = model
                st.session_state.last_model_meta = meta
                st.success("Checkpoint loaded into session as last_model.")
            except Exception as e:
                st.error("Failed to load checkpoint into model: " + str(e))

# ---------- Tab: Diagrams & Examples ----------
with tabs[6]:
    st.header("Neural Network Diagrams & Example Code")
    st.write("Generate simple diagrams for architectures and show small example snippets you can copy-paste.")
    diagram_type = st.selectbox("Diagram type", ["Feedforward (MLP)","ConvNet small"])
    if diagram_type == "Feedforward (MLP)":
        in_size = st.number_input("Input size", value=64)
        hidden = st.text_input("Hidden layers (comma)", value="32,16")
        hidden_layers = [int(x.strip()) for x in hidden.split(',') if x.strip()]
        out_size = st.number_input("Output size", value=10)
        if st.button("Show diagram"):
            dot = draw_feedforward_diagram(in_size, hidden_layers, out_size)
            st.graphviz_chart(dot)
            st.code(f"""# Example MLP (PyTorch)
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear({in_size}, {hidden_layers[0]})
        ...
""")
    else:
        h = st.number_input("Image height", value=28)
        w = st.number_input("Image width", value=28)
        convs = st.text_input("Conv channels (comma)", value="16,32")
        conv_channels = [int(x.strip()) for x in convs.split(',') if x.strip()]
        fc = st.text_input("FC layers (comma)", value="64")
        fc_layers = [int(x.strip()) for x in fc.split(',') if x.strip()]
        if st.button("Show conv diagram"):
            dot = draw_conv_diagram((h,w), conv_channels, fc_layers)
            st.graphviz_chart(dot)
            st.code("""# ConvNet example (PyTorch)
class CNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        ...
""")

# ---------------------------
# End of app
# ---------------------------
st.sidebar.markdown("""
**Next steps / notes**
- For production save: save meta + model + optimizer state.
- For large datasets (MNIST/CIFAR) run on a machine with GPU.
- This app is educational and designed to be easily extended.
""")
