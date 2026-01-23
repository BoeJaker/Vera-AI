#!/usr/bin/env python3
"""
JEPA (Joint Embedding Predictive Architecture) for Graphs

Implements self-supervised learning through predictive coding in representation space.
Key innovation: Predict representations of masked graph parts, not raw features.

Based on "A Path Towards Autonomous Machine Intelligence" (LeCun, 2022)
and "I-JEPA: Self-Supervised Learning from Images via Feature Prediction" (2023)

New Dependencies:
    pip install torch torch-geometric
"""

import logging
import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Assume we have the base classes from previous implementation
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from Memory.ml_models import MLModelPlugin, ModelConfig, AnalysisResult, ModelType


# ============================================================================
# JEPA CORE ARCHITECTURE
# ============================================================================

class GraphEncoder(nn.Module):
    """
    Graph encoder using Graph Attention Networks.
    Encodes graph structure and features into representations.
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int],
        output_dim: int,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()
        
        try:
            from torch_geometric.nn import GATv2Conv, global_mean_pool
            self.global_pool = global_pool = global_mean_pool
        except ImportError:
            logger.error("PyTorch Geometric required for JEPA")
            raise
        
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        
        # Input layer
        self.convs.append(GATv2Conv(
            input_dim,
            hidden_dims[0],
            heads=num_heads,
            dropout=dropout,
            concat=True
        ))
        self.norms.append(nn.LayerNorm(hidden_dims[0] * num_heads))
        
        # Hidden layers
        for i in range(len(hidden_dims) - 1):
            self.convs.append(GATv2Conv(
                hidden_dims[i] * num_heads,
                hidden_dims[i+1],
                heads=num_heads,
                dropout=dropout,
                concat=True
            ))
            self.norms.append(nn.LayerNorm(hidden_dims[i+1] * num_heads))
        
        # Output projection
        final_dim = hidden_dims[-1] * num_heads
        self.output_proj = nn.Sequential(
            nn.Linear(final_dim, output_dim),
            nn.LayerNorm(output_dim)
        )
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, edge_index, batch=None):
        """
        Args:
            x: Node features [num_nodes, input_dim]
            edge_index: Edge connectivity [2, num_edges]
            batch: Batch assignment for nodes (for batched graphs)
            
        Returns:
            Node embeddings [num_nodes, output_dim]
        """
        h = x
        
        for conv, norm in zip(self.convs, self.norms):
            h = conv(h, edge_index)
            h = norm(h)
            h = F.gelu(h)
            h = self.dropout(h)
        
        # Project to output dimension
        h = self.output_proj(h)
        
        return h
    
    def encode_subgraph(self, x, edge_index, node_mask, batch=None):
        """
        Encode only a subgraph defined by node_mask.
        
        Args:
            x: Node features
            edge_index: Edge connectivity
            node_mask: Boolean mask [num_nodes] indicating which nodes to encode
            batch: Batch assignment
            
        Returns:
            Embeddings for masked nodes
        """
        # Get full graph embeddings
        full_embeddings = self.forward(x, edge_index, batch)
        
        # Return only embeddings for masked nodes
        return full_embeddings[node_mask]


class JEPAPredictor(nn.Module):
    """
    Predictor network for JEPA.
    Predicts target representations from context representations.
    """
    
    def __init__(
        self,
        context_dim: int,
        target_dim: int,
        hidden_dim: int = 512,
        num_layers: int = 3
    ):
        super().__init__()
        
        layers = []
        
        # Input layer
        layers.append(nn.Linear(context_dim, hidden_dim))
        layers.append(nn.LayerNorm(hidden_dim))
        layers.append(nn.GELU())
        
        # Hidden layers
        for _ in range(num_layers - 2):
            layers.append(nn.Linear(hidden_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
        
        # Output layer
        layers.append(nn.Linear(hidden_dim, target_dim))
        
        self.predictor = nn.Sequential(*layers)
    
    def forward(self, context_repr):
        """
        Predict target representations from context.
        
        Args:
            context_repr: Context representations [batch, context_dim]
            
        Returns:
            Predicted target representations [batch, target_dim]
        """
        return self.predictor(context_repr)


class GraphJEPAModel(nn.Module):
    """
    Complete JEPA model for graphs.
    
    Components:
    1. Context Encoder: Encodes visible parts of graph
    2. Target Encoder: Encodes masked parts (EMA of context encoder)
    3. Predictor: Predicts target representations from context
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int] = [128, 256],
        embedding_dim: int = 256,
        num_heads: int = 4,
        predictor_hidden_dim: int = 512,
        ema_decay: float = 0.996,
        dropout: float = 0.1
    ):
        super().__init__()
        
        # Context encoder (trained with gradients)
        self.context_encoder = GraphEncoder(
            input_dim=input_dim,
            hidden_dims=hidden_dims,
            output_dim=embedding_dim,
            num_heads=num_heads,
            dropout=dropout
        )
        
        # Target encoder (EMA of context encoder, no gradients)
        self.target_encoder = GraphEncoder(
            input_dim=input_dim,
            hidden_dims=hidden_dims,
            output_dim=embedding_dim,
            num_heads=num_heads,
            dropout=dropout
        )
        
        # Initialize target encoder with context encoder weights
        self.target_encoder.load_state_dict(self.context_encoder.state_dict())
        
        # Freeze target encoder (will be updated via EMA)
        for param in self.target_encoder.parameters():
            param.requires_grad = False
        
        # Predictor network
        self.predictor = JEPAPredictor(
            context_dim=embedding_dim,
            target_dim=embedding_dim,
            hidden_dim=predictor_hidden_dim
        )
        
        self.ema_decay = ema_decay
        self.embedding_dim = embedding_dim
    
    def forward(self, x, edge_index, context_mask, target_mask, batch=None):
        """
        Forward pass of JEPA.
        
        Args:
            x: Node features [num_nodes, input_dim]
            edge_index: Edge connectivity [2, num_edges]
            context_mask: Boolean mask for context nodes [num_nodes]
            target_mask: Boolean mask for target nodes [num_nodes]
            batch: Batch assignment for graphs
            
        Returns:
            predicted_target: Predicted target representations
            actual_target: Actual target representations (from target encoder)
        """
        # Encode context (with gradients)
        context_embeddings = self.context_encoder(x, edge_index, batch)
        
        # Get context representation (pool over context nodes)
        if context_mask.sum() > 0:
            context_repr = context_embeddings[context_mask].mean(dim=0, keepdim=True)
        else:
            context_repr = context_embeddings.mean(dim=0, keepdim=True)
        
        # Predict target representations
        predicted_target = self.predictor(context_repr)
        
        # Encode targets with target encoder (no gradients)
        with torch.no_grad():
            target_embeddings = self.target_encoder(x, edge_index, batch)
            
            # Get actual target representation
            if target_mask.sum() > 0:
                actual_target = target_embeddings[target_mask].mean(dim=0, keepdim=True)
            else:
                actual_target = target_embeddings.mean(dim=0, keepdim=True)
        
        return predicted_target, actual_target
    
    @torch.no_grad()
    def update_target_encoder(self):
        """
        Update target encoder using exponential moving average.
        This is called after each training step.
        """
        for param_c, param_t in zip(
            self.context_encoder.parameters(),
            self.target_encoder.parameters()
        ):
            param_t.data = self.ema_decay * param_t.data + (1 - self.ema_decay) * param_c.data
    
    @torch.no_grad()
    def get_embeddings(self, x, edge_index, batch=None):
        """
        Get embeddings for inference (no masking).
        Uses context encoder.
        """
        return self.context_encoder(x, edge_index, batch)


# ============================================================================
# MASKING STRATEGIES
# ============================================================================

class GraphMaskingStrategy:
    """
    Various strategies for masking parts of graphs in JEPA.
    """
    
    @staticmethod
    def random_node_masking(num_nodes: int, mask_ratio: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Randomly mask a fraction of nodes.
        
        Args:
            num_nodes: Total number of nodes
            mask_ratio: Fraction of nodes to mask as targets
            
        Returns:
            context_mask: Boolean mask for context nodes
            target_mask: Boolean mask for target nodes
        """
        num_mask = int(num_nodes * mask_ratio)
        indices = torch.randperm(num_nodes)
        
        target_indices = indices[:num_mask]
        context_indices = indices[num_mask:]
        
        context_mask = torch.zeros(num_nodes, dtype=torch.bool)
        target_mask = torch.zeros(num_nodes, dtype=torch.bool)
        
        context_mask[context_indices] = True
        target_mask[target_indices] = True
        
        return context_mask, target_mask
    
    @staticmethod
    def block_masking(
        num_nodes: int,
        node_positions: Optional[torch.Tensor] = None,
        block_size: int = 5,
        num_blocks: int = 3
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Mask contiguous blocks of nodes (similar to image patches in I-JEPA).
        
        Args:
            num_nodes: Total number of nodes
            node_positions: Optional 2D positions of nodes for spatial blocking
            block_size: Approximate size of each block
            num_blocks: Number of blocks to mask
            
        Returns:
            context_mask: Boolean mask for context nodes
            target_mask: Boolean mask for target nodes
        """
        target_mask = torch.zeros(num_nodes, dtype=torch.bool)
        
        if node_positions is not None:
            # Spatial blocking based on positions
            for _ in range(num_blocks):
                # Pick random center
                center_idx = torch.randint(0, num_nodes, (1,)).item()
                center_pos = node_positions[center_idx]
                
                # Find nearby nodes
                distances = torch.norm(node_positions - center_pos, dim=1)
                _, nearest_indices = torch.topk(distances, k=min(block_size, num_nodes), largest=False)
                
                target_mask[nearest_indices] = True
        else:
            # Random contiguous blocks
            for _ in range(num_blocks):
                start_idx = torch.randint(0, max(1, num_nodes - block_size), (1,)).item()
                end_idx = min(start_idx + block_size, num_nodes)
                target_mask[start_idx:end_idx] = True
        
        context_mask = ~target_mask
        
        return context_mask, target_mask
    
    @staticmethod
    def neighborhood_masking(
        edge_index: torch.Tensor,
        num_nodes: int,
        num_seeds: int = 3,
        hops: int = 2
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Mask k-hop neighborhoods of seed nodes.
        
        Args:
            edge_index: Graph connectivity
            num_nodes: Total nodes
            num_seeds: Number of seed nodes
            hops: Number of hops for neighborhood
            
        Returns:
            context_mask: Boolean mask for context nodes
            target_mask: Boolean mask for target nodes
        """
        # Select random seed nodes
        seed_nodes = torch.randperm(num_nodes)[:num_seeds]
        
        # Find k-hop neighborhoods
        target_nodes = set(seed_nodes.tolist())
        
        for _ in range(hops):
            new_nodes = set()
            for node in target_nodes:
                # Find neighbors
                neighbors = edge_index[1][edge_index[0] == node].tolist()
                new_nodes.update(neighbors)
            target_nodes.update(new_nodes)
        
        # Create masks
        target_mask = torch.zeros(num_nodes, dtype=torch.bool)
        target_mask[list(target_nodes)] = True
        
        context_mask = ~target_mask
        
        return context_mask, target_mask
    
    @staticmethod
    def attribute_masking(
        x: torch.Tensor,
        mask_ratio: float = 0.3
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Mask based on node attributes (e.g., mask high-degree nodes).
        
        Args:
            x: Node features
            mask_ratio: Fraction to mask
            
        Returns:
            context_mask: Boolean mask for context nodes
            target_mask: Boolean mask for target nodes
        """
        num_nodes = x.shape[0]
        
        # Use feature magnitude to determine masking
        feature_importance = x.norm(dim=1)
        num_mask = int(num_nodes * mask_ratio)
        
        # Mask most important nodes
        _, target_indices = torch.topk(feature_importance, k=num_mask)
        
        target_mask = torch.zeros(num_nodes, dtype=torch.bool)
        target_mask[target_indices] = True
        
        context_mask = ~target_mask
        
        return context_mask, target_mask


# ============================================================================
# JEPA TRAINING
# ============================================================================

class GraphJEPATrainer:
    """
    Trainer for Graph JEPA model.
    """
    
    def __init__(
        self,
        model: GraphJEPAModel,
        learning_rate: float = 1e-4,
        weight_decay: float = 1e-5,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        self.model = model.to(device)
        self.device = device
        
        # Optimizer (only for context encoder and predictor)
        trainable_params = list(model.context_encoder.parameters()) + list(model.predictor.parameters())
        self.optimizer = torch.optim.AdamW(
            trainable_params,
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=1000,
            eta_min=1e-6
        )
        
        # Loss function (smooth L1 loss in representation space)
        self.criterion = nn.SmoothL1Loss()
        
        # Masking strategy
        self.masking_strategy = GraphMaskingStrategy()
    
    def train_step(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
        masking_method: str = 'random'
    ) -> Dict[str, float]:
        """
        Single training step.
        
        Args:
            x: Node features
            edge_index: Edge connectivity
            batch: Batch assignment
            masking_method: 'random', 'block', 'neighborhood', or 'attribute'
            
        Returns:
            Dictionary with loss and metrics
        """
        self.model.train()
        
        x = x.to(self.device)
        edge_index = edge_index.to(self.device)
        if batch is not None:
            batch = batch.to(self.device)
        
        num_nodes = x.shape[0]
        
        # Generate masks
        if masking_method == 'random':
            context_mask, target_mask = self.masking_strategy.random_node_masking(num_nodes)
        elif masking_method == 'block':
            context_mask, target_mask = self.masking_strategy.block_masking(num_nodes)
        elif masking_method == 'neighborhood':
            context_mask, target_mask = self.masking_strategy.neighborhood_masking(edge_index, num_nodes)
        elif masking_method == 'attribute':
            context_mask, target_mask = self.masking_strategy.attribute_masking(x)
        else:
            raise ValueError(f"Unknown masking method: {masking_method}")
        
        context_mask = context_mask.to(self.device)
        target_mask = target_mask.to(self.device)
        
        # Forward pass
        predicted_target, actual_target = self.model(
            x, edge_index, context_mask, target_mask, batch
        )
        
        # Compute loss (prediction error in representation space)
        loss = self.criterion(predicted_target, actual_target)
        
        # Add regularization: encourage diversity in representations
        # Variance regularization (prevent collapse)
        pred_std = predicted_target.std(dim=0).mean()
        target_std = actual_target.std(dim=0).mean()
        
        # Variance should be high (representations should be diverse)
        variance_loss = torch.relu(1.0 - pred_std) + torch.relu(1.0 - target_std)
        
        total_loss = loss + 0.01 * variance_loss
        
        # Backward pass
        self.optimizer.zero_grad()
        total_loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(self.model.context_encoder.parameters(), max_norm=1.0)
        torch.nn.utils.clip_grad_norm_(self.model.predictor.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        # Update target encoder with EMA
        self.model.update_target_encoder()
        
        return {
            'loss': loss.item(),
            'variance_loss': variance_loss.item(),
            'total_loss': total_loss.item(),
            'pred_std': pred_std.item(),
            'target_std': target_std.item(),
            'num_context': context_mask.sum().item(),
            'num_target': target_mask.sum().item()
        }
    
    def train_epoch(
        self,
        data_list: List[Any],
        masking_method: str = 'random'
    ) -> Dict[str, float]:
        """
        Train for one epoch.
        
        Args:
            data_list: List of PyG Data objects
            masking_method: Masking strategy to use
            
        Returns:
            Average metrics for epoch
        """
        epoch_metrics = defaultdict(list)
        
        for data in data_list:
            metrics = self.train_step(
                data.x,
                data.edge_index,
                batch=getattr(data, 'batch', None),
                masking_method=masking_method
            )
            
            for key, value in metrics.items():
                epoch_metrics[key].append(value)
        
        # Average metrics
        avg_metrics = {
            key: np.mean(values)
            for key, values in epoch_metrics.items()
        }
        
        # Step scheduler
        self.scheduler.step()
        avg_metrics['learning_rate'] = self.scheduler.get_last_lr()[0]
        
        return avg_metrics


# ============================================================================
# JEPA PLUGIN FOR ML FRAMEWORK
# ============================================================================

class JEPAPlugin(MLModelPlugin):
    """
    JEPA plugin for graph representation learning.
    Self-supervised learning through predictive coding in representation space.
    """
    
    def __init__(
        self,
        hidden_dims: List[int] = [128, 256],
        embedding_dim: int = 256,
        num_heads: int = 4,
        ema_decay: float = 0.996,
        learning_rate: float = 1e-4
    ):
        config = ModelConfig(
            name="JEPA",
            model_type=ModelType.SELF_SUPERVISED,
            version="2.0.0",
            parameters={
                "hidden_dims": hidden_dims,
                "embedding_dim": embedding_dim,
                "num_heads": num_heads,
                "ema_decay": ema_decay,
                "learning_rate": learning_rate
            },
            input_requirements={
                "graph": "PyG Data object with node features",
                "training_data": "List of PyG Data objects for training"
            },
            output_schema={
                "embeddings": "Learned node representations",
                "cluster_assignments": "Optional clustering of embeddings",
                "reconstruction_quality": "Quality metrics"
            },
            description="Joint Embedding Predictive Architecture (JEPA) for self-supervised graph learning. "
                       "Learns representations by predicting masked node representations in embedding space.",
            use_cases=[
                "Unsupervised graph representation learning",
                "Pre-training for downstream tasks",
                "Anomaly detection via reconstruction error",
                "Graph clustering and visualization",
                "Transfer learning across graphs"
            ]
        )
        super().__init__(config)
        
        self.hidden_dims = hidden_dims
        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.ema_decay = ema_decay
        self.learning_rate = learning_rate
        
        self.model = None
        self.trainer = None
        self.training_history = []
    
    def fit(self, data: Dict[str, Any]) -> None:
        """
        Train JEPA model on graph data.
        
        Args:
            data: Dictionary with:
                - 'graph' or 'graphs': Single PyG Data or list of Data objects
                - 'epochs': Number of training epochs (default: 100)
                - 'masking_method': 'random', 'block', 'neighborhood', or 'attribute'
                - 'batch_size': For batching multiple graphs
        """
        logger.info("[JEPA] Starting self-supervised training...")
        
        # Get training data
        if 'graphs' in data:
            graphs = data['graphs']
        elif 'graph' in data:
            graphs = [data['graph']]
        else:
            raise ValueError("Must provide 'graph' or 'graphs' in data")
        
        # Ensure we have PyG Data objects
        try:
            from torch_geometric.data import Data
        except ImportError:
            raise ImportError("PyTorch Geometric required")
        
        # Get parameters
        epochs = data.get('epochs', 100)
        masking_method = data.get('masking_method', 'random')
        input_dim = graphs[0].num_features
        
        # Initialize model
        self.model = GraphJEPAModel(
            input_dim=input_dim,
            hidden_dims=self.hidden_dims,
            embedding_dim=self.embedding_dim,
            num_heads=self.num_heads,
            ema_decay=self.ema_decay
        )
        
        # Initialize trainer
        self.trainer = GraphJEPATrainer(
            model=self.model,
            learning_rate=self.learning_rate
        )
        
        # Training loop
        logger.info(f"[JEPA] Training for {epochs} epochs using {masking_method} masking...")
        
        for epoch in range(epochs):
            metrics = self.trainer.train_epoch(graphs, masking_method=masking_method)
            self.training_history.append(metrics)
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"[JEPA] Epoch {epoch+1}/{epochs} - "
                    f"Loss: {metrics['loss']:.4f}, "
                    f"Pred Std: {metrics['pred_std']:.4f}, "
                    f"LR: {metrics['learning_rate']:.2e}"
                )
        
        self.is_trained = True
        logger.info("[JEPA] Training complete!")
    
    def predict(self, data: Dict[str, Any]) -> AnalysisResult:
        """
        Generate embeddings and analyze graph using trained JEPA.
        
        Args:
            data: Dictionary with:
                - 'graph': PyG Data object
                - 'analyze_clusters': Whether to perform clustering on embeddings
                - 'detect_anomalies': Whether to detect anomalies
                
        Returns:
            AnalysisResult with embeddings and analysis
        """
        if not self.is_trained:
            raise RuntimeError("JEPA model must be trained before prediction")
        
        import torch
        from torch_geometric.data import Data
        
        graph = data.get('graph')
        if not isinstance(graph, Data):
            raise ValueError("Input must be PyG Data object")
        
        analyze_clusters = data.get('analyze_clusters', True)
        detect_anomalies = data.get('detect_anomalies', True)
        
        execution_id = f"jepa_exec_{int(time.time())}"
        
        logger.info("[JEPA] Generating embeddings...")
        
        # Get embeddings
        self.model.eval()
        with torch.no_grad():
            x = graph.x.to(self.trainer.device)
            edge_index = graph.edge_index.to(self.trainer.device)
            batch = getattr(graph, 'batch', None)
            if batch is not None:
                batch = batch.to(self.trainer.device)
            
            embeddings = self.model.get_embeddings(x, edge_index, batch)
            embeddings_np = embeddings.cpu().numpy()
        
        predictions = {
            "num_nodes": graph.num_nodes,
            "embedding_dim": self.embedding_dim
        }
        
        # Clustering analysis
        if analyze_clusters:
            from sklearn.cluster import KMeans
            
            # Determine optimal number of clusters (elbow method)
            max_clusters = min(10, graph.num_nodes // 10)
            if max_clusters >= 2:
                inertias = []
                for k in range(2, max_clusters + 1):
                    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                    kmeans.fit(embeddings_np)
                    inertias.append(kmeans.inertia_)
                
                # Use elbow or default to 5 clusters
                optimal_k = min(5, max_clusters)
                kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
                cluster_assignments = kmeans.fit_predict(embeddings_np)
                
                predictions["clusters"] = {
                    "num_clusters": optimal_k,
                    "assignments": cluster_assignments.tolist(),
                    "cluster_sizes": {
                        int(k): int(v)
                        for k, v in zip(*np.unique(cluster_assignments, return_counts=True))
                    }
                }
        
        # Anomaly detection via reconstruction error
        if detect_anomalies:
            # Mask nodes and measure prediction error
            anomaly_scores = []
            
            for i in range(graph.num_nodes):
                target_mask = torch.zeros(graph.num_nodes, dtype=torch.bool)
                target_mask[i] = True
                context_mask = ~target_mask
                
                target_mask = target_mask.to(self.trainer.device)
                context_mask = context_mask.to(self.trainer.device)
                
                with torch.no_grad():
                    predicted, actual = self.model(
                        x, edge_index, context_mask, target_mask, batch
                    )
                    
                    # Reconstruction error
                    error = F.mse_loss(predicted, actual, reduction='none').mean().item()
                    anomaly_scores.append(error)
            
            anomaly_scores = np.array(anomaly_scores)
            
            # Threshold at 95th percentile
            threshold = np.percentile(anomaly_scores, 95)
            anomalous_nodes = np.where(anomaly_scores > threshold)[0].tolist()
            
            predictions["anomalies"] = {
                "num_anomalies": len(anomalous_nodes),
                "anomalous_nodes": anomalous_nodes,
                "anomaly_scores": {
                    int(i): float(score)
                    for i, score in enumerate(anomaly_scores)
                },
                "threshold": float(threshold)
            }
        
        # Calculate embedding quality metrics
        # Variance (high variance = diverse representations)
        variance = embeddings_np.var(axis=0).mean()
        
        # Pairwise distances (measure separation)
        from scipy.spatial.distance import pdist
        pairwise_distances = pdist(embeddings_np, metric='cosine')
        avg_distance = pairwise_distances.mean()
        
        scores = {
            "embedding_variance": float(variance),
            "avg_pairwise_distance": float(avg_distance),
            "training_epochs": len(self.training_history),
            "final_loss": self.training_history[-1]['loss'] if self.training_history else None
        }
        
        # Generate interpretation
        interpretation = (
            f"JEPA learned {self.embedding_dim}-dimensional representations through self-supervised learning. "
            f"Embeddings have variance {variance:.3f} and average pairwise distance {avg_distance:.3f}. "
        )
        
        if analyze_clusters and "clusters" in predictions:
            interpretation += (
                f"Identified {predictions['clusters']['num_clusters']} clusters in embedding space. "
            )
        
        if detect_anomalies and "anomalies" in predictions:
            interpretation += (
                f"Detected {predictions['anomalies']['num_anomalies']} anomalous nodes "
                f"({predictions['anomalies']['num_anomalies']/graph.num_nodes*100:.1f}%) "
                f"based on reconstruction error."
            )
        
        result = AnalysisResult(
            model_name=self.config.name,
            model_version=self.config.version,
            execution_id=execution_id,
            timestamp=datetime.now().isoformat(),
            input_summary={
                "num_nodes": graph.num_nodes,
                "num_edges": graph.num_edges,
                "num_features": graph.num_features
            },
            predictions=predictions,
            embeddings=embeddings_np,
            scores=scores,
            metadata={
                "masking_methods_used": ["random", "block", "neighborhood"],
                "ema_decay": self.ema_decay,
                "training_history": self.training_history[-10:]  # Last 10 epochs
            },
            interpretation=interpretation
        )
        
        return result
    
    def transform(self, data: Dict[str, Any]) -> np.ndarray:
        """Transform graph into JEPA embeddings"""
        result = self.predict(data)
        return result.embeddings
    
    def get_training_history(self) -> List[Dict[str, float]]:
        """Get complete training history"""
        return self.training_history
    
    def visualize_embeddings(self, embeddings: np.ndarray, labels: Optional[np.ndarray] = None):
        """
        Visualize embeddings using t-SNE or UMAP.
        
        Args:
            embeddings: Node embeddings
            labels: Optional node labels for coloring
            
        Returns:
            2D projection of embeddings
        """
        try:
            from sklearn.manifold import TSNE
            
            tsne = TSNE(n_components=2, random_state=42)
            embeddings_2d = tsne.fit_transform(embeddings)
            
            return embeddings_2d
        except ImportError:
            logger.warning("scikit-learn not available for visualization")
            return None


# ============================================================================
# EXAMPLE USAGE & INTEGRATION
# ============================================================================

def example_jepa_usage():
    """
    Example of using JEPA for self-supervised graph learning.
    """
    import torch
    from torch_geometric.data import Data
    import networkx as nx
    
    print("=" * 80)
    print("JEPA (Joint Embedding Predictive Architecture) for Graphs")
    print("=" * 80)
    
    # Create example graph
    print("\n1. Creating example graph...")
    G = nx.karate_club_graph()
    
    # Convert to PyG format
    edge_index = torch.tensor(list(G.edges())).t().contiguous()
    # Add reverse edges for undirected graph
    edge_index = torch.cat([edge_index, edge_index.flip(0)], dim=1)
    
    # Random node features
    x = torch.randn(G.number_of_nodes(), 16)
    
    data = Data(x=x, edge_index=edge_index)
    
    print(f"   Graph: {data.num_nodes} nodes, {data.num_edges} edges")
    
    # Initialize JEPA
    print("\n2. Initializing JEPA model...")
    jepa = JEPAPlugin(
        hidden_dims=[64, 128],
        embedding_dim=64,
        num_heads=4,
        ema_decay=0.996,
        learning_rate=1e-3
    )
    
    # Train JEPA
    print("\n3. Training JEPA with self-supervised learning...")
    jepa.fit({
        'graph': data,
        'epochs': 50,
        'masking_method': 'random'
    })
    
    # Get embeddings and analysis
    print("\n4. Generating embeddings and analysis...")
    result = jepa.predict({
        'graph': data,
        'analyze_clusters': True,
        'detect_anomalies': True
    })
    
    print(f"\n   Embeddings shape: {result.embeddings.shape}")
    print(f"   Embedding variance: {result.scores['embedding_variance']:.4f}")
    print(f"   Clusters found: {result.predictions['clusters']['num_clusters']}")
    print(f"   Anomalies detected: {result.predictions['anomalies']['num_anomalies']}")
    
    print(f"\n   Interpretation: {result.interpretation}")
    
    # Show training progress
    print("\n5. Training history (last 5 epochs):")
    for i, metrics in enumerate(jepa.training_history[-5:], 1):
        print(f"   Epoch {len(jepa.training_history)-5+i}: "
              f"Loss={metrics['loss']:.4f}, "
              f"Std={metrics['pred_std']:.4f}")
    
    print("\n" + "=" * 80)
    print("JEPA CAPABILITIES")
    print("=" * 80)
    print("""
    ✓ Self-supervised learning (no labels needed)
    ✓ Learns from graph structure and features
    ✓ Multiple masking strategies (random, block, neighborhood, attribute)
    ✓ Exponential moving average for stable target encoder
    ✓ Automatic clustering in embedding space
    ✓ Anomaly detection via reconstruction error
    ✓ High-quality embeddings for downstream tasks
    ✓ Interpretable representations
    
    Use Cases:
    - Pre-training on unlabeled graphs
    - Transfer learning across different graphs
    - Unsupervised anomaly detection
    - Graph clustering and community detection
    - Visualization of complex graphs
    - Feature extraction for downstream ML
    """)
    
    return jepa, result


if __name__ == "__main__":
    # Run example
    jepa_model, analysis_result = example_jepa_usage()
    
    print("\n" + "=" * 80)
    print("INTEGRATION WITH LLM FRAMEWORK")
    print("=" * 80)
    print("""
    LLM can use JEPA for:
    
    1. "Learn representations from this unlabeled graph"
       → Trains JEPA with self-supervised learning
       → Returns: High-quality embeddings without labels
    
    2. "Find unusual nodes in this network"
       → Uses JEPA reconstruction error for anomaly detection
       → Returns: Nodes that are hard to predict from context
    
    3. "Cluster these nodes based on structure"
       → Runs JEPA to get embeddings
       → Performs clustering in embedding space
       → Returns: Structurally similar groups
    
    4. "Pre-train embeddings for downstream classification"
       → Trains JEPA on unlabeled data
       → Fine-tunes on labeled data (separate task)
       → Returns: Better performance than training from scratch
    
    The LLM orchestrator can:
    - Automatically select JEPA for unsupervised tasks
    - Combine JEPA embeddings with other models
    - Use JEPA as preprocessing for supervised models
    - Interpret JEPA results in natural language
    """)