"""
Security Testing Tools (Burp Suite Integration) and Machine Learning Tools
for LLM Agent System
"""

import os
import json
import base64
import requests
import subprocess
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd

# ML Libraries
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
except:
    TORCH_AVAILABLE = False

try:
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.decomposition import PCA
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except:
    TRANSFORMERS_AVAILABLE = False


# ============================================================================
# BURP SUITE TOOLS - Security Testing
# ============================================================================

class BurpSuiteInput(BaseModel):
    """Input for Burp Suite operations."""
    operation: str = Field(..., description="Operation: scan, spider, proxy_history, send_to_repeater, or intruder")
    target_url: Optional[str] = Field(None, description="Target URL for scanning/spidering")
    burp_api_url: str = Field(default="http://127.0.0.1:1337", description="Burp Suite REST API URL")
    api_key: Optional[str] = Field(None, description="Burp Suite API key if required")
    parameters: Optional[str] = Field(None, description="Additional parameters as JSON")


class ProxyRequestInput(BaseModel):
    """Input for proxy request manipulation."""
    request_data: str = Field(..., description="HTTP request data to send through proxy")
    proxy_url: str = Field(default="http://127.0.0.1:8080", description="Burp Suite proxy URL")
    method: str = Field(default="GET", description="HTTP method")


class WebSecurityScanInput(BaseModel):
    """Input for web security scanning."""
    target_url: str = Field(..., description="Target URL to scan")
    scan_type: str = Field(default="passive", description="Scan type: passive, active, or full")
    check_types: Optional[List[str]] = Field(None, description="Specific vulnerability checks to run")


class BurpSuiteTools:
    """Tools for integrating with Burp Suite Professional/Community Edition."""
    
    def __init__(self, agent):
        self.agent = agent
    
    def burp_suite_scan(self, operation: str, target_url: Optional[str] = None,
                        burp_api_url: str = "http://127.0.0.1:1337",
                        api_key: Optional[str] = None,
                        parameters: Optional[str] = None) -> str:
        """
        Interface with Burp Suite for security testing.
        
        Operations:
        - scan: Start active scan on target
        - spider: Spider/crawl target
        - proxy_history: Get proxy history
        - sitemap: Get discovered sitemap
        - issues: Get identified security issues
        
        Requires: Burp Suite Professional with REST API enabled
        """
        try:
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            operation = operation.lower()
            params = json.loads(parameters) if parameters else {}
            
            if operation == "scan":
                if not target_url:
                    return "[Error] target_url required for scan operation"
                
                # Start active scan
                payload = {
                    "urls": [target_url],
                    "scan_type": params.get("scan_type", "active")
                }
                
                response = requests.post(
                    f"{burp_api_url}/v0.1/scan",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 201:
                    scan_id = response.json().get("scan_id")
                    
                    # Store in memory
                    mem = self.agent.mem.add_session_memory(
                        self.agent.sess.id,
                        f"Burp scan started: {target_url}",
                        "security_scan",
                        {"scan_id": scan_id, "target": target_url, "tool": "burp"}
                    )
                    
                    return f"✓ Scan started successfully\nScan ID: {scan_id}\nTarget: {target_url}"
                else:
                    return f"[Error] Scan failed: {response.status_code} - {response.text}"
            
            elif operation == "spider":
                if not target_url:
                    return "[Error] target_url required for spider operation"
                
                payload = {"baseUrl": target_url}
                response = requests.post(
                    f"{burp_api_url}/v0.1/spider",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 201:
                    return f"✓ Spider started on {target_url}"
                else:
                    return f"[Error] Spider failed: {response.status_code}"
            
            elif operation == "issues":
                response = requests.get(
                    f"{burp_api_url}/v0.1/scan/issues",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    issues = response.json().get("issues", [])
                    
                    if not issues:
                        return "No security issues found"
                    
                    output = [f"Found {len(issues)} security issues:\n"]
                    
                    for idx, issue in enumerate(issues[:20], 1):
                        severity = issue.get("severity", "Unknown")
                        name = issue.get("name", "Unknown")
                        url = issue.get("url", "")
                        
                        output.append(f"{idx}. [{severity}] {name}")
                        output.append(f"   URL: {url}")
                        output.append("")
                    
                    if len(issues) > 20:
                        output.append(f"... [{len(issues) - 20} more issues]")
                    
                    return "\n".join(output)
                else:
                    return f"[Error] Failed to retrieve issues: {response.status_code}"
            
            elif operation == "sitemap":
                response = requests.get(
                    f"{burp_api_url}/v0.1/sitemap",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    sitemap = response.json().get("sitemap", [])
                    
                    output = [f"Sitemap contains {len(sitemap)} URLs:\n"]
                    for url in sitemap[:50]:
                        output.append(f"  {url}")
                    
                    if len(sitemap) > 50:
                        output.append(f"... [{len(sitemap) - 50} more URLs]")
                    
                    return "\n".join(output)
                else:
                    return f"[Error] Failed to retrieve sitemap: {response.status_code}"
            
            elif operation == "proxy_history":
                # Note: This requires Burp Extender API or manual export
                return ("[Info] Proxy history retrieval requires Burp Extender API.\n"
                       "Alternative: Export proxy history from Burp Suite manually.")
            
            else:
                return f"[Error] Unknown operation: {operation}"
                
        except requests.RequestException as e:
            return f"[Burp API Error] {str(e)}\nEnsure Burp Suite is running with REST API enabled."
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def web_security_scan(self, target_url: str, scan_type: str = "passive",
                          check_types: Optional[List[str]] = None) -> str:
        """
        Perform web security scanning using various tools.
        
        Scan types:
        - passive: Non-intrusive checks (headers, SSL, info disclosure)
        - active: Active vulnerability testing (requires authorization)
        - full: Comprehensive scan (passive + active)
        
        Check types: xss, sqli, csrf, headers, ssl, cors, etc.
        """
        try:
            results = []
            results.append(f"Security Scan Report for: {target_url}")
            results.append("=" * 70)
            
            scan_type = scan_type.lower()
            
            # Passive checks
            if scan_type in ["passive", "full"]:
                # Check HTTP headers
                try:
                    response = requests.get(target_url, timeout=10, verify=False)
                    
                    results.append("\n[+] HTTP Headers Analysis:")
                    
                    # Security headers check
                    security_headers = {
                        'X-Frame-Options': 'Protects against clickjacking',
                        'X-Content-Type-Options': 'Prevents MIME sniffing',
                        'Strict-Transport-Security': 'Enforces HTTPS',
                        'Content-Security-Policy': 'Prevents XSS attacks',
                        'X-XSS-Protection': 'Browser XSS filter',
                    }
                    
                    for header, purpose in security_headers.items():
                        if header in response.headers:
                            results.append(f"  ✓ {header}: {response.headers[header][:50]}")
                        else:
                            results.append(f"  ✗ Missing {header} ({purpose})")
                    
                    # Check for sensitive info disclosure
                    results.append("\n[+] Information Disclosure Check:")
                    disclosure_headers = ['Server', 'X-Powered-By', 'X-AspNet-Version']
                    
                    for header in disclosure_headers:
                        if header in response.headers:
                            results.append(f"  ⚠ {header} disclosed: {response.headers[header]}")
                    
                except Exception as e:
                    results.append(f"\n[Error] HTTP check failed: {str(e)}")
            
            # Active checks (requires authorization)
            if scan_type in ["active", "full"]:
                results.append("\n[+] Active Scanning:")
                results.append("  ⚠ Active scanning requires proper authorization")
                results.append("  ⚠ Use Burp Suite or ZAP for comprehensive active scanning")
            
            # Store results
            report = "\n".join(results)
            
            mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Security scan: {target_url}",
                "security_scan",
                {"target": target_url, "scan_type": scan_type}
            )
            
            return report
            
        except Exception as e:
            return f"[Security Scan Error] {str(e)}"
    
    def proxy_request(self, request_data: str, proxy_url: str = "http://127.0.0.1:8080",
                      method: str = "GET") -> str:
        """
        Send HTTP request through Burp Suite proxy for interception and analysis.
        Useful for testing request manipulation and observing responses.
        """
        try:
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Parse request data
            lines = request_data.strip().split('\n')
            if not lines:
                return "[Error] Invalid request data"
            
            # Extract URL from first line or use as full URL
            if lines[0].startswith('http'):
                url = lines[0]
                headers = {}
                body = ""
            else:
                # Try to parse as raw HTTP request
                return "[Error] Provide full URL or raw HTTP request"
            
            response = requests.request(
                method=method.upper(),
                url=url,
                proxies=proxies,
                verify=False,
                timeout=30
            )
            
            output = [
                "Request sent through Burp Suite proxy",
                f"Status: {response.status_code}",
                f"Check Burp Suite for intercepted request/response",
                "\nResponse preview:",
                "-" * 40,
                response.text[:500]
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Proxy Error] {str(e)}\nEnsure Burp Suite proxy is running on {proxy_url}"


# ============================================================================
# MACHINE LEARNING TOOLS
# ============================================================================

class MLTrainInput(BaseModel):
    """Input for ML model training."""
    data_path: str = Field(..., description="Path to training data (CSV)")
    target_column: str = Field(..., description="Name of target/label column")
    model_type: str = Field(..., description="Model type: random_forest, gradient_boost, logistic, svm, neural_net")
    test_size: float = Field(default=0.2, description="Proportion of data for testing")
    save_path: Optional[str] = Field(None, description="Path to save trained model")


class MLPredictInput(BaseModel):
    """Input for ML predictions."""
    model_path: str = Field(..., description="Path to saved model")
    data_path: str = Field(..., description="Path to data for prediction (CSV)")


class MLClusterInput(BaseModel):
    """Input for clustering operations."""
    data_path: str = Field(..., description="Path to data (CSV)")
    algorithm: str = Field(default="kmeans", description="Algorithm: kmeans, dbscan")
    n_clusters: int = Field(default=3, description="Number of clusters (for kmeans)")


class TextMLInput(BaseModel):
    """Input for text/NLP ML operations."""
    text: str = Field(..., description="Text to analyze")
    operation: str = Field(..., description="Operation: sentiment, summarize, classify, ner, qa")
    parameters: Optional[str] = Field(None, description="Additional parameters as JSON")


class ImageMLInput(BaseModel):
    """Input for image ML operations."""
    image_path: str = Field(..., description="Path to image file")
    operation: str = Field(..., description="Operation: classify, detect_objects, caption")
    model_name: Optional[str] = Field(None, description="Specific model to use")


class MachineLearningTools:
    """Tools for machine learning tasks: training, prediction, clustering, and inference."""
    
    def __init__(self, agent):
        self.agent = agent
        self.models = {}  # Cache for loaded models
    
    def train_ml_model(self, data_path: str, target_column: str,
                       model_type: str, test_size: float = 0.2,
                       save_path: Optional[str] = None) -> str:
        """
        Train machine learning model on structured data.
        
        Supported models:
        - random_forest: Random Forest Classifier
        - gradient_boost: Gradient Boosting Classifier  
        - logistic: Logistic Regression
        - svm: Support Vector Machine
        - neural_net: Simple Neural Network (requires PyTorch)
        
        Returns training metrics and saves model if save_path provided.
        """
        try:
            if not SKLEARN_AVAILABLE:
                return "[Error] scikit-learn not installed. Run: pip install scikit-learn"
            
            # Load data
            df = pd.read_csv(data_path)
            
            if target_column not in df.columns:
                return f"[Error] Target column '{target_column}' not found in data"
            
            # Prepare data
            X = df.drop(columns=[target_column])
            y = df[target_column]
            
            # Handle categorical variables
            categorical_cols = X.select_dtypes(include=['object']).columns
            for col in categorical_cols:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
            
            # Encode target if categorical
            if y.dtype == 'object':
                le_target = LabelEncoder()
                y = le_target.fit_transform(y)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Select and train model
            model_type = model_type.lower()
            
            if model_type == "random_forest":
                model = RandomForestClassifier(n_estimators=100, random_state=42)
            elif model_type == "gradient_boost":
                model = GradientBoostingClassifier(n_estimators=100, random_state=42)
            elif model_type == "logistic":
                model = LogisticRegression(max_iter=1000, random_state=42)
            elif model_type == "svm":
                model = SVC(kernel='rbf', random_state=42)
            elif model_type == "neural_net":
                if not TORCH_AVAILABLE:
                    return "[Error] PyTorch not installed. Run: pip install torch"
                return self._train_neural_net(X_train_scaled, X_test_scaled, y_train, y_test, save_path)
            else:
                return f"[Error] Unknown model type: {model_type}"
            
            # Train
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            report = classification_report(y_test, y_pred)
            
            # Save model
            if save_path:
                import joblib
                joblib.dump({
                    'model': model,
                    'scaler': scaler,
                    'feature_names': X.columns.tolist()
                }, save_path)
            
            # Store in memory
            mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Trained {model_type} model",
                "ml_training",
                {"accuracy": accuracy, "model_type": model_type, "data": data_path}
            )
            
            output = [
                f"Model Training Complete: {model_type}",
                "=" * 50,
                f"Data: {data_path}",
                f"Samples: {len(df)} ({len(X_train)} train, {len(X_test)} test)",
                f"Features: {X.shape[1]}",
                f"\nAccuracy: {accuracy:.4f}",
                f"\nClassification Report:",
                "-" * 50,
                report
            ]
            
            if save_path:
                output.append(f"\n✓ Model saved to: {save_path}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[ML Training Error] {str(e)}"
    
    def _train_neural_net(self, X_train, X_test, y_train, y_test, save_path):
        """Train a simple neural network using PyTorch."""
        try:
            # Convert to tensors
            X_train_t = torch.FloatTensor(X_train)
            X_test_t = torch.FloatTensor(X_test)
            y_train_t = torch.LongTensor(y_train)
            y_test_t = torch.LongTensor(y_test)
            
            # Define simple network
            input_size = X_train.shape[1]
            num_classes = len(np.unique(y_train))
            
            class SimpleNN(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.fc1 = nn.Linear(input_size, 64)
                    self.fc2 = nn.Linear(64, 32)
                    self.fc3 = nn.Linear(32, num_classes)
                    self.relu = nn.ReLU()
                    
                def forward(self, x):
                    x = self.relu(self.fc1(x))
                    x = self.relu(self.fc2(x))
                    return self.fc3(x)
            
            model = SimpleNN()
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
            
            # Train
            epochs = 50
            for epoch in range(epochs):
                model.train()
                optimizer.zero_grad()
                outputs = model(X_train_t)
                loss = criterion(outputs, y_train_t)
                loss.backward()
                optimizer.step()
            
            # Evaluate
            model.eval()
            with torch.no_grad():
                outputs = model(X_test_t)
                _, predicted = torch.max(outputs, 1)
                accuracy = (predicted == y_test_t).sum().item() / len(y_test_t)
            
            if save_path:
                torch.save(model.state_dict(), save_path)
            
            return f"Neural Network trained\nAccuracy: {accuracy:.4f}\nEpochs: {epochs}"
            
        except Exception as e:
            return f"[Neural Net Error] {str(e)}"
    
    def predict_ml(self, model_path: str, data_path: str) -> str:
        """
        Make predictions using trained model.
        Loads model and applies to new data.
        """
        try:
            if not SKLEARN_AVAILABLE:
                return "[Error] scikit-learn not installed"
            
            import joblib
            
            # Load model
            model_data = joblib.load(model_path)
            model = model_data['model']
            scaler = model_data['scaler']
            feature_names = model_data.get('feature_names', [])
            
            # Load data
            df = pd.read_csv(data_path)
            
            # Prepare data
            X = df[feature_names] if feature_names else df
            
            # Handle categoricals
            categorical_cols = X.select_dtypes(include=['object']).columns
            for col in categorical_cols:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
            
            # Scale
            X_scaled = scaler.transform(X)
            
            # Predict
            predictions = model.predict(X_scaled)
            
            # Get probabilities if available
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(X_scaled)
                df['prediction'] = predictions
                df['confidence'] = probabilities.max(axis=1)
            else:
                df['prediction'] = predictions
            
            # Save results
            output_path = data_path.replace('.csv', '_predictions.csv')
            df.to_csv(output_path, index=False)
            
            output = [
                "Predictions Complete",
                "=" * 50,
                f"Model: {model_path}",
                f"Data: {data_path}",
                f"Samples: {len(df)}",
                f"\nPredictions saved to: {output_path}",
                f"\nSample predictions:",
                "-" * 50,
                df.head(10).to_string()
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[ML Prediction Error] {str(e)}"
    
    def cluster_data(self, data_path: str, algorithm: str = "kmeans",
                     n_clusters: int = 3) -> str:
        """
        Perform clustering on data.
        
        Algorithms:
        - kmeans: K-Means clustering
        - dbscan: DBSCAN density-based clustering
        
        Returns cluster assignments and statistics.
        """
        try:
            if not SKLEARN_AVAILABLE:
                return "[Error] scikit-learn not installed"
            
            # Load data
            df = pd.read_csv(data_path)
            X = df.select_dtypes(include=[np.number])
            
            if X.empty:
                return "[Error] No numeric columns found for clustering"
            
            # Scale data
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            algorithm = algorithm.lower()
            
            if algorithm == "kmeans":
                clusterer = KMeans(n_clusters=n_clusters, random_state=42)
                labels = clusterer.fit_predict(X_scaled)
                
            elif algorithm == "dbscan":
                clusterer = DBSCAN(eps=0.5, min_samples=5)
                labels = clusterer.fit_predict(X_scaled)
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                
            else:
                return f"[Error] Unknown algorithm: {algorithm}"
            
            # Add cluster labels to dataframe
            df['cluster'] = labels
            
            # Save results
            output_path = data_path.replace('.csv', '_clustered.csv')
            df.to_csv(output_path, index=False)
            
            # Get cluster statistics
            cluster_stats = df.groupby('cluster').size()
            
            output = [
                f"Clustering Complete: {algorithm}",
                "=" * 50,
                f"Data: {data_path}",
                f"Samples: {len(df)}",
                f"Clusters found: {n_clusters}",
                f"\nCluster sizes:",
                "-" * 40,
                cluster_stats.to_string(),
                f"\n✓ Results saved to: {output_path}"
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Clustering Error] {str(e)}"
    
    def text_ml_operation(self, text: str, operation: str,
                          parameters: Optional[str] = None) -> str:
        """
        Perform NLP/text ML operations using transformers.
        
        Operations:
        - sentiment: Sentiment analysis
        - summarize: Text summarization
        - classify: Zero-shot classification
        - ner: Named Entity Recognition
        - qa: Question answering
        
        Requires: transformers library
        """
        try:
            if not TRANSFORMERS_AVAILABLE:
                return "[Error] transformers not installed. Run: pip install transformers"
            
            operation = operation.lower()
            params = json.loads(parameters) if parameters else {}
            
            if operation == "sentiment":
                analyzer = pipeline("sentiment-analysis")
                result = analyzer(text[:512])[0]  # Limit text length
                return f"Sentiment: {result['label']}\nConfidence: {result['score']:.4f}"
            
            elif operation == "summarize":
                summarizer = pipeline("summarization")
                result = summarizer(text, max_length=130, min_length=30, do_sample=False)[0]
                return f"Summary:\n{result['summary_text']}"
            
            elif operation == "classify":
                labels = params.get("labels", ["positive", "negative", "neutral"])
                classifier = pipeline("zero-shot-classification")
                result = classifier(text, candidate_labels=labels)
                
                output = ["Classification Results:"]
                for label, score in zip(result['labels'], result['scores']):
                    output.append(f"  {label}: {score:.4f}")
                return "\n".join(output)
            
            elif operation == "ner":
                ner = pipeline("ner", grouped_entities=True)
                entities = ner(text)
                
                if not entities:
                    return "No entities found"
                
                output = ["Named Entities:"]
                for ent in entities:
                    output.append(f"  {ent['word']}: {ent['entity_group']} ({ent['score']:.3f})")
                return "\n".join(output)
            
            elif operation == "qa":
                question = params.get("question")
                if not question:
                    return "[Error] 'question' parameter required for QA"
                
                qa_pipeline = pipeline("question-answering")
                result = qa_pipeline(question=question, context=text)
                return f"Answer: {result['answer']}\nConfidence: {result['score']:.4f}"
            
            else:
                return f"[Error] Unknown operation: {operation}"
                
        except Exception as e:
            return f"[Text ML Error] {str(e)}"
    
    def image_ml_operation(self, image_path: str, operation: str,
                           model_name: Optional[str] = None) -> str:
        """
        Perform image ML operations.
        
        Operations:
        - classify: Image classification
        - detect_objects: Object detection
        - caption: Image captioning
        
        Requires: transformers, PIL
        """
        try:
            if not TRANSFORMERS_AVAILABLE:
                return "[Error] transformers not installed"
            
            from PIL import Image
            
            if not os.path.exists(image_path):
                return f"[Error] Image not found: {image_path}"
            
            image = Image.open(image_path)
            operation = operation.lower()
            
            if operation == "classify":
                classifier = pipeline("image-classification")
                results = classifier(image)
                
                output = ["Image Classification Results:"]
                for r in results[:5]:
                    output.append(f"  {r['label']}: {r['score']:.4f}")
                return "\n".join(output)
            
            elif operation == "detect_objects":
                detector = pipeline("object-detection")
                results = detector(image)
                
                output = [f"Detected {len(results)} objects:"]
                for r in results[:10]:
                    output.append(f"  {r['label']}: {r['score']:.3f} at {r['box']}")
                return "\n".join(output)
            
            elif operation == "caption":
                captioner = pipeline("image-to-text")
                result = captioner(image)[0]
                return f"Caption: {result['generated_text']}"
            
            else:
                return f"[Error] Unknown operation: {operation}"
                
        except Exception as e:
            return f"[Image ML Error] {str(e)}"


# ============================================================================
# TOOL LOADER FUNCTIONS
# ============================================================================

def SecurityToolLoader(agent):
    """Load Burp Suite and security testing tools."""
    from langchain_core.tools import StructuredTool
    
    tools = BurpSuiteTools(agent)
    
    return [
        StructuredTool.from_function(
            func=tools.burp_suite_scan,
            name="burp_suite",
            description="Interface with Burp Suite for security testing: scan, spider, get issues. Requires Burp Pro with REST API.",
            args_schema=BurpSuiteInput
        ),
        StructuredTool.from_function(
            func=tools.web_security_scan,
            name="web_security_scan",
            description="Perform web security scanning: check headers, SSL, vulnerabilities. Passive and active modes.",
            args_schema=WebSecurityScanInput
        ),
        StructuredTool.from_function(
            func=tools.proxy_request,
            name="proxy_request",
            description="Send HTTP request through Burp Suite proxy for interception and analysis.",
            args_schema=ProxyRequestInput
        ),
    ]


def MLToolLoader(agent):
    """Load machine learning and AI tools."""
    from langchain_core.tools import StructuredTool
    
    tools = MachineLearningTools(agent)
    
    return [
        StructuredTool.from_function(
            func=tools.train_ml_model,
            name="train_ml_model",
            description="Train ML models on CSV data: random_forest, gradient_boost, logistic, svm, neural_net. Returns accuracy metrics.",
            args_schema=MLTrainInput
        ),
        StructuredTool.from_function(
            func=tools.predict_ml,
            name="predict_ml",
            description="Make predictions using trained ML model. Loads model and applies to new data.",
            args_schema=MLPredictInput
        ),
        StructuredTool.from_function(
            func=tools.cluster_data,
            name="cluster_data",
            description="Perform clustering on data using kmeans or dbscan. Returns cluster assignments.",
            args_schema=MLClusterInput
        ),
        StructuredTool.from_function(
            func=tools.text_ml_operation,
            name="text_ml",
            description="NLP operations: sentiment analysis, summarization, classification, NER, QA. Uses transformers.",
            args_schema=TextMLInput
        ),
        StructuredTool.from_function(
            func=tools.image_ml_operation,
            name="image_ml",
            description="Image ML operations: classification, object detection, captioning. Uses transformers.",
            args_schema=ImageMLInput
        ),
    ]


# ============================================================================
# ADVANCED SECURITY TOOLS
# ============================================================================

class AdvancedSecurityTools:
    """Additional security testing and analysis tools."""
    
    def __init__(self, agent):
        self.agent = agent
    
    def port_scan(self, target: str, ports: str = "common") -> str:
        """
        Scan ports on target host.
        WARNING: Only use on systems you own or have permission to test.
        """
        try:
            import socket
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Common ports
            common_ports = {
                21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
                53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
                443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
                5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Proxy",
                8443: "HTTPS-Alt", 27017: "MongoDB"
            }
            
            if ports == "common":
                port_list = list(common_ports.keys())
            else:
                # Parse port range (e.g., "1-1000" or "80,443,8080")
                if '-' in ports:
                    start, end = map(int, ports.split('-'))
                    port_list = range(start, end + 1)
                else:
                    port_list = [int(p.strip()) for p in ports.split(',')]
            
            def check_port(port):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((target, port))
                    sock.close()
                    return port, result == 0
                except:
                    return port, False
            
            output = [f"Port Scan Results for {target}"]
            output.append("=" * 60)
            open_ports = []
            
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = {executor.submit(check_port, port): port for port in port_list}
                
                for future in as_completed(futures):
                    port, is_open = future.result()
                    if is_open:
                        service = common_ports.get(port, "Unknown")
                        output.append(f"✓ Port {port} OPEN - {service}")
                        open_ports.append(port)
            
            if not open_ports:
                output.append("No open ports found")
            else:
                output.append(f"\nTotal open ports: {len(open_ports)}")
            
            # Store in memory
            mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Port scan: {target}",
                "security_scan",
                {"target": target, "open_ports": open_ports}
            )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Port Scan Error] {str(e)}"
    
    def ssl_analysis(self, target: str) -> str:
        """
        Analyze SSL/TLS configuration of a target.
        Checks certificate, protocols, ciphers.
        """
        try:
            import ssl
            import socket
            from datetime import datetime
            
            context = ssl.create_default_context()
            
            # Parse target
            if '://' in target:
                target = target.split('://')[1]
            if '/' in target:
                target = target.split('/')[0]
            
            host = target.split(':')[0]
            port = int(target.split(':')[1]) if ':' in target else 443
            
            output = [f"SSL/TLS Analysis for {host}:{port}"]
            output.append("=" * 60)
            
            # Get certificate
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Certificate info
                    output.append("\n[+] Certificate Information:")
                    output.append(f"  Subject: {dict(x[0] for x in cert['subject'])}")
                    output.append(f"  Issuer: {dict(x[0] for x in cert['issuer'])}")
                    output.append(f"  Valid from: {cert['notBefore']}")
                    output.append(f"  Valid until: {cert['notAfter']}")
                    
                    # Check expiry
                    expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_left = (expiry - datetime.now()).days
                    
                    if days_left < 0:
                        output.append(f"  ⚠ EXPIRED {abs(days_left)} days ago!")
                    elif days_left < 30:
                        output.append(f"  ⚠ Expires in {days_left} days")
                    else:
                        output.append(f"  ✓ Valid for {days_left} more days")
                    
                    # Protocol and cipher
                    output.append(f"\n[+] Connection Information:")
                    output.append(f"  Protocol: {version}")
                    output.append(f"  Cipher: {cipher[0]}")
                    output.append(f"  Bits: {cipher[2]}")
                    
                    # Check for weak protocols
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        output.append(f"  ⚠ WARNING: Weak protocol {version} detected")
                    else:
                        output.append(f"  ✓ Using secure protocol")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[SSL Analysis Error] {str(e)}"
    
    def payload_fuzzer(self, url: str, payload_type: str = "xss") -> str:
        """
        Fuzz endpoint with common payloads.
        WARNING: Only use on systems you own or have permission to test.
        
        Payload types: xss, sqli, cmd_injection, path_traversal
        """
        try:
            payloads = {
                "xss": [
                    "<script>alert('XSS')</script>",
                    "<img src=x onerror=alert('XSS')>",
                    "javascript:alert('XSS')",
                    "<svg onload=alert('XSS')>",
                ],
                "sqli": [
                    "' OR '1'='1",
                    "' OR 1=1--",
                    "admin'--",
                    "' UNION SELECT NULL--",
                    "1' AND '1'='1",
                ],
                "cmd_injection": [
                    "; ls -la",
                    "| whoami",
                    "`cat /etc/passwd`",
                    "$(whoami)",
                ],
                "path_traversal": [
                    "../../../etc/passwd",
                    "..\\..\\..\\windows\\system32\\config\\sam",
                    "....//....//....//etc/passwd",
                ],
            }
            
            if payload_type not in payloads:
                return f"[Error] Unknown payload type. Available: {', '.join(payloads.keys())}"
            
            output = [f"Payload Fuzzing: {url}"]
            output.append(f"Type: {payload_type}")
            output.append("=" * 60)
            output.append("⚠ Use only on authorized targets!")
            output.append("")
            
            results = []
            
            for payload in payloads[payload_type]:
                try:
                    # Try GET parameter
                    test_url = f"{url}?test={payload}"
                    response = requests.get(test_url, timeout=5)
                    
                    # Check if payload reflected
                    if payload in response.text:
                        results.append(f"✓ REFLECTED: {payload[:50]}")
                    
                    # Check for errors
                    error_indicators = ['error', 'exception', 'syntax', 'warning']
                    if any(ind in response.text.lower() for ind in error_indicators):
                        results.append(f"⚠ ERROR GENERATED: {payload[:50]}")
                    
                except Exception as e:
                    results.append(f"✗ FAILED: {payload[:50]} - {str(e)[:30]}")
            
            output.extend(results)
            output.append(f"\nTested {len(payloads[payload_type])} payloads")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Fuzzer Error] {str(e)}"
    
    def dns_enumeration(self, domain: str) -> str:
        """
        Enumerate DNS records for a domain.
        Queries A, AAAA, MX, NS, TXT, CNAME records.
        """
        try:
            import dns.resolver
            
            output = [f"DNS Enumeration for {domain}"]
            output.append("=" * 60)
            
            record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA']
            
            for record_type in record_types:
                try:
                    answers = dns.resolver.resolve(domain, record_type)
                    output.append(f"\n[+] {record_type} Records:")
                    
                    for rdata in answers:
                        if record_type == 'MX':
                            output.append(f"  {rdata.preference} {rdata.exchange}")
                        else:
                            output.append(f"  {rdata}")
                            
                except dns.resolver.NoAnswer:
                    output.append(f"\n[-] {record_type} Records: None found")
                except Exception as e:
                    output.append(f"\n[!] {record_type} Records: Error - {str(e)[:50]}")
            
            return "\n".join(output)
            
        except ImportError:
            return "[Error] dnspython not installed. Run: pip install dnspython"
        except Exception as e:
            return f"[DNS Enumeration Error] {str(e)}"


# ============================================================================
# ADVANCED ML TOOLS
# ============================================================================

class AdvancedMLTools:
    """Advanced machine learning capabilities."""
    
    def __init__(self, agent):
        self.agent = agent
    
    def anomaly_detection(self, data_path: str, method: str = "isolation_forest") -> str:
        """
        Detect anomalies in data using various methods.
        
        Methods:
        - isolation_forest: Isolation Forest algorithm
        - one_class_svm: One-Class SVM
        - statistical: Z-score based detection
        """
        try:
            if not SKLEARN_AVAILABLE:
                return "[Error] scikit-learn not installed"
            
            from sklearn.ensemble import IsolationForest
            from sklearn.svm import OneClassSVM
            from scipy import stats
            
            # Load data
            df = pd.read_csv(data_path)
            X = df.select_dtypes(include=[np.number])
            
            if X.empty:
                return "[Error] No numeric columns found"
            
            method = method.lower()
            
            if method == "isolation_forest":
                model = IsolationForest(contamination=0.1, random_state=42)
                predictions = model.fit_predict(X)
                
            elif method == "one_class_svm":
                model = OneClassSVM(nu=0.1)
                predictions = model.fit_predict(X)
                
            elif method == "statistical":
                # Z-score method
                z_scores = np.abs(stats.zscore(X))
                predictions = np.where((z_scores > 3).any(axis=1), -1, 1)
                
            else:
                return f"[Error] Unknown method: {method}"
            
            # Add predictions to dataframe
            df['is_anomaly'] = predictions == -1
            anomalies = df[df['is_anomaly']]
            
            # Save results
            output_path = data_path.replace('.csv', '_anomalies.csv')
            df.to_csv(output_path, index=False)
            
            output = [
                f"Anomaly Detection: {method}",
                "=" * 60,
                f"Data: {data_path}",
                f"Total samples: {len(df)}",
                f"Anomalies found: {len(anomalies)} ({len(anomalies)/len(df)*100:.2f}%)",
                f"\nTop anomalies:",
                "-" * 60,
                anomalies.head(10).to_string(),
                f"\n✓ Results saved to: {output_path}"
            ]
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Anomaly Detection Error] {str(e)}"
    
    def time_series_forecast(self, data_path: str, target_column: str,
                             periods: int = 10) -> str:
        """
        Forecast time series data using Prophet or ARIMA.
        Requires properly formatted time series data with date column.
        """
        try:
            # Load data
            df = pd.read_csv(data_path)
            
            if target_column not in df.columns:
                return f"[Error] Target column '{target_column}' not found"
            
            # Try using simple linear extrapolation
            y = df[target_column].values
            X = np.arange(len(y)).reshape(-1, 1)
            
            from sklearn.linear_model import LinearRegression
            
            model = LinearRegression()
            model.fit(X, y)
            
            # Forecast
            future_X = np.arange(len(y), len(y) + periods).reshape(-1, 1)
            forecast = model.predict(future_X)
            
            output = [
                "Time Series Forecast",
                "=" * 60,
                f"Data: {data_path}",
                f"Target: {target_column}",
                f"Historical points: {len(y)}",
                f"Forecast periods: {periods}",
                "\nForecasted values:",
                "-" * 40
            ]
            
            for i, val in enumerate(forecast, 1):
                output.append(f"  Period +{i}: {val:.2f}")
            
            # Store forecast
            forecast_df = pd.DataFrame({
                'period': range(1, periods + 1),
                'forecast': forecast
            })
            output_path = data_path.replace('.csv', '_forecast.csv')
            forecast_df.to_csv(output_path, index=False)
            
            output.append(f"\n✓ Forecast saved to: {output_path}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Forecast Error] {str(e)}"
    
    def feature_importance(self, data_path: str, target_column: str) -> str:
        """
        Analyze feature importance for prediction task.
        Uses Random Forest to determine which features matter most.
        """
        try:
            if not SKLEARN_AVAILABLE:
                return "[Error] scikit-learn not installed"
            
            # Load data
            df = pd.read_csv(data_path)
            
            if target_column not in df.columns:
                return f"[Error] Target column '{target_column}' not found"
            
            X = df.drop(columns=[target_column])
            y = df[target_column]
            
            # Handle categoricals
            categorical_cols = X.select_dtypes(include=['object']).columns
            for col in categorical_cols:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
            
            # Train Random Forest
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X, y)
            
            # Get feature importance
            importances = model.feature_importances_
            feature_names = X.columns
            
            # Sort by importance
            indices = np.argsort(importances)[::-1]
            
            output = [
                "Feature Importance Analysis",
                "=" * 60,
                f"Data: {data_path}",
                f"Target: {target_column}",
                f"Features analyzed: {len(feature_names)}",
                "\nTop features (by importance):",
                "-" * 60
            ]
            
            for i, idx in enumerate(indices[:20], 1):
                output.append(f"{i:2d}. {feature_names[idx]:30s}: {importances[idx]:.4f}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Feature Importance Error] {str(e)}"


# Combine all loaders
def CombinedSecurityMLToolLoader(agent):
    """Load both security and ML tools together."""
    security_tools = SecurityToolLoader(agent)
    ml_tools = MLToolLoader(agent)
    return security_tools + ml_tools