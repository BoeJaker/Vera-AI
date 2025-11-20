/**
 * GraphLoader - A 3D evolving polygonal graph loading animation
 * Theme-aware component that reads CSS variables from VeraChat themes
 * 
 * Usage:
 *   const loader = new GraphLoader('#container', { nodeCount: 12 });
 *   loader.show();
 *   loader.hide();
 *   loader.destroy();
 * 
 * Or as overlay:
 *   GraphLoader.showOverlay('Loading graph...');
 *   GraphLoader.hideOverlay();
 */

class GraphLoader {
  static overlayInstance = null;

  constructor(container, options = {}) {
    this.container = typeof container === 'string' 
      ? document.querySelector(container) 
      : container;
    
    if (!this.container) {
      console.error('GraphLoader: Container not found');
      return;
    }

    // Configuration with defaults
    this.config = {
      nodeCount: options.nodeCount || 12,
      baseRadius: options.baseRadius || 100,
      rotationSpeed: options.rotationSpeed || 0.003,
      nodeSize: options.nodeSize || 4,
      edgeOpacity: options.edgeOpacity || 0.4,
      width: options.width || 300,
      height: options.height || 300,
      showText: options.showText !== false,
      showProgress: options.showProgress !== false,
      text: options.text || 'Initializing',
      introEnabled: options.introEnabled !== false,
      introDuration: options.introDuration || 2.5, // seconds for V->sphere unfurl
      ...options
    };

    this.nodes = [];
    this.edges = [];
    this.animationId = null;
    this.startTime = null;
    this.rotationX = 0;
    this.rotationY = 0;
    this.lastEvolution = 0;
    this.isVisible = false;
    this.introPhase = true; // Start in intro phase
    this.introProgress = 0;

    this._createElements();
    this._initializeGraph();
  }

  // Get theme colors from CSS variables
  _getThemeColors() {
    const style = getComputedStyle(document.documentElement);
    return {
      primary: style.getPropertyValue('--accent')?.trim() || '#6366f1',
      secondary: style.getPropertyValue('--accent-muted')?.trim() || '#8b5cf6',
      text: style.getPropertyValue('--text')?.trim() || '#94a3b8',
      bg: style.getPropertyValue('--bg')?.trim() || '#0f172a',
      panelBg: style.getPropertyValue('--panel-bg')?.trim() || '#1e293b',
      border: style.getPropertyValue('--border')?.trim() || '#334155'
    };
  }

  _createElements() {
    const colors = this._getThemeColors();

    // Main wrapper
    this.wrapper = document.createElement('div');
    this.wrapper.className = 'graph-loader-wrapper';
    this.wrapper.innerHTML = `
      <style>
        .graph-loader-wrapper {
          display: none;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          min-height: 200px;
          background: var(--bg, ${colors.bg});
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 100;
          transition: opacity 0.4s ease;
        }
        
        .graph-loader-wrapper.active {
          display: flex;
        }
        
        .graph-loader-wrapper.fade-out {
          opacity: 0;
          pointer-events: none;
        }
        
        /* Ensure parent container is positioned for absolute child */
        #graph:has(.graph-loader-wrapper) {
          position: relative;
        }
        
        .graph-loader-container {
          position: relative;
          width: ${this.config.width}px;
          height: ${this.config.height}px;
        }
        
        .graph-loader-canvas {
          width: 100%;
          height: 100%;
          filter: drop-shadow(0 0 20px color-mix(in srgb, var(--accent, ${colors.primary}) 30%, transparent));
        }
        
        .graph-loader-glow {
          position: absolute;
          width: 66%;
          height: 66%;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background: radial-gradient(circle, color-mix(in srgb, var(--accent, ${colors.primary}) 15%, transparent) 0%, transparent 70%);
          border-radius: 50%;
          pointer-events: none;
          animation: graph-loader-pulse 3s ease-in-out infinite;
        }
        
        @keyframes graph-loader-pulse {
          0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
          50% { transform: translate(-50%, -50%) scale(1.2); opacity: 0.8; }
        }
        
        .graph-loader-text {
          margin-top: 24px;
          color: var(--text, ${colors.text});
          font-size: 12px;
          letter-spacing: 2px;
          text-transform: uppercase;
          font-family: inherit;
          animation: graph-loader-text-fade 2s ease-in-out infinite;
        }
        
        @keyframes graph-loader-text-fade {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
        
        .graph-loader-progress {
          width: 150px;
          height: 2px;
          background: var(--border, ${colors.border});
          border-radius: 1px;
          margin-top: 12px;
          overflow: hidden;
        }
        
        .graph-loader-progress-fill {
          height: 100%;
          width: 30%;
          background: linear-gradient(90deg, 
            var(--accent, ${colors.primary}), 
            var(--accent-muted, ${colors.secondary}), 
            var(--accent, ${colors.primary})
          );
          background-size: 200% 100%;
          border-radius: 1px;
          animation: graph-loader-progress-flow 1.5s ease-in-out infinite;
        }
        
        @keyframes graph-loader-progress-flow {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }

        /* Overlay mode */
        .graph-loader-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 10000;
          background: color-mix(in srgb, var(--bg, ${colors.bg}) 95%, transparent);
          backdrop-filter: blur(4px);
        }
      </style>
      
      <div class="graph-loader-container">
        <div class="graph-loader-glow"></div>
        <canvas class="graph-loader-canvas"></canvas>
      </div>
      ${this.config.showText ? `<div class="graph-loader-text">${this.config.text}</div>` : ''}
      ${this.config.showProgress ? `
        <div class="graph-loader-progress">
          <div class="graph-loader-progress-fill"></div>
        </div>
      ` : ''}
    `;

    this.container.appendChild(this.wrapper);
    
    this.canvas = this.wrapper.querySelector('.graph-loader-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.canvas.width = this.config.width * 2; // Retina
    this.canvas.height = this.config.height * 2;
    this.ctx.scale(2, 2);
    
    this.textEl = this.wrapper.querySelector('.graph-loader-text');
  }

  _initializeGraph() {
    this.nodes = [];
    this.edges = [];
    
    // Create nodes distributed on a sphere
    for (let i = 0; i < this.config.nodeCount; i++) {
      this.nodes.push(new GraphLoaderNode(i, this.config.nodeCount, this.config.baseRadius));
    }
    
    this._generateConnections();
  }

  _generateConnections() {
    this.edges = [];
    
    for (let i = 0; i < this.nodes.length; i++) {
      const distances = [];
      for (let j = 0; j < this.nodes.length; j++) {
        if (i !== j) {
          const dx = this.nodes[i].x - this.nodes[j].x;
          const dy = this.nodes[i].y - this.nodes[j].y;
          const dz = this.nodes[i].z - this.nodes[j].z;
          distances.push({ index: j, dist: Math.sqrt(dx*dx + dy*dy + dz*dz) });
        }
      }
      distances.sort((a, b) => a.dist - b.dist);
      
      const connectionCount = 2 + Math.floor(Math.random() * 3);
      for (let k = 0; k < connectionCount && k < distances.length; k++) {
        const j = distances[k].index;
        if (!this.edges.some(e => 
          (e.nodeA === this.nodes[i] && e.nodeB === this.nodes[j]) ||
          (e.nodeA === this.nodes[j] && e.nodeB === this.nodes[i])
        )) {
          this.edges.push(new GraphLoaderEdge(this.nodes[i], this.nodes[j]));
        }
      }
    }
  }

  _evolveGraph(time) {
    if (time - this.lastEvolution > 5) {
      this.lastEvolution = time;
      
      if (Math.random() > 0.5 && this.edges.length > this.config.nodeCount) {
        this.edges.splice(Math.floor(Math.random() * this.edges.length), 1);
      } else if (this.edges.length < this.config.nodeCount * 3) {
        const nodeA = this.nodes[Math.floor(Math.random() * this.nodes.length)];
        const nodeB = this.nodes[Math.floor(Math.random() * this.nodes.length)];
        if (nodeA !== nodeB && !this.edges.some(e => 
          (e.nodeA === nodeA && e.nodeB === nodeB) ||
          (e.nodeA === nodeB && e.nodeB === nodeA)
        )) {
          this.edges.push(new GraphLoaderEdge(nodeA, nodeB));
        }
      }
    }
  }

  _drawEdge(edge, opacity) {
    const colors = this._getThemeColors();
    const centerX = this.config.width / 2;
    const centerY = this.config.height / 2;
    
    const avgZ = (edge.nodeA.z + edge.nodeB.z) / 2;
    const depthFade = 0.3 + 0.7 * ((avgZ + this.config.baseRadius) / (this.config.baseRadius * 2));
    
    this.ctx.beginPath();
    this.ctx.moveTo(edge.nodeA.screenX, edge.nodeA.screenY);
    this.ctx.lineTo(edge.nodeB.screenX, edge.nodeB.screenY);
    
    const gradient = this.ctx.createLinearGradient(
      edge.nodeA.screenX, edge.nodeA.screenY,
      edge.nodeB.screenX, edge.nodeB.screenY
    );
    
    const alpha = opacity * depthFade * this.config.edgeOpacity;
    const primaryRgb = this._hexToRgb(colors.primary);
    const secondaryRgb = this._hexToRgb(colors.secondary);
    
    gradient.addColorStop(0, `rgba(${primaryRgb}, ${alpha})`);
    gradient.addColorStop(0.5, `rgba(${secondaryRgb}, ${alpha * 1.2})`);
    gradient.addColorStop(1, `rgba(${primaryRgb}, ${alpha})`);
    
    this.ctx.strokeStyle = gradient;
    this.ctx.lineWidth = 1.5 * Math.min(edge.nodeA.scale, edge.nodeB.scale);
    this.ctx.stroke();
  }

  _drawNode(node, time) {
    const colors = this._getThemeColors();
    const pulse = 1 + 0.3 * Math.sin(time * 3 + node.pulseOffset);
    const size = this.config.nodeSize * node.scale * pulse;
    const depthFade = 0.4 + 0.6 * ((node.z + this.config.baseRadius) / (this.config.baseRadius * 2));

    const primaryRgb = this._hexToRgb(colors.primary);
    const secondaryRgb = this._hexToRgb(colors.secondary);

    // Outer glow
    const glowGradient = this.ctx.createRadialGradient(
      node.screenX, node.screenY, 0,
      node.screenX, node.screenY, size * 4
    );
    glowGradient.addColorStop(0, `rgba(${primaryRgb}, ${0.4 * depthFade})`);
    glowGradient.addColorStop(0.5, `rgba(${secondaryRgb}, ${0.1 * depthFade})`);
    glowGradient.addColorStop(1, `rgba(${secondaryRgb}, 0)`);
    
    this.ctx.beginPath();
    this.ctx.arc(node.screenX, node.screenY, size * 4, 0, Math.PI * 2);
    this.ctx.fillStyle = glowGradient;
    this.ctx.fill();

    // Core node
    const coreGradient = this.ctx.createRadialGradient(
      node.screenX - size * 0.3, node.screenY - size * 0.3, 0,
      node.screenX, node.screenY, size
    );
    coreGradient.addColorStop(0, `rgba(255, 255, 255, ${0.9 * depthFade})`);
    coreGradient.addColorStop(0.3, `rgba(${primaryRgb}, ${0.8 * depthFade})`);
    coreGradient.addColorStop(1, `rgba(${secondaryRgb}, ${0.6 * depthFade})`);
    
    this.ctx.beginPath();
    this.ctx.arc(node.screenX, node.screenY, size, 0, Math.PI * 2);
    this.ctx.fillStyle = coreGradient;
    this.ctx.fill();
  }

  _hexToRgb(hex) {
    if (!hex) return '99, 102, 241';
    hex = hex.replace('#', '');
    if (hex.length === 3) {
      hex = hex.split('').map(c => c + c).join('');
    }
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `${r}, ${g}, ${b}`;
  }

  _animate = (timestamp) => {
    if (!this.isVisible) return;
    
    if (!this.startTime) this.startTime = timestamp;
    const time = (timestamp - this.startTime) / 1000;

    const centerX = this.config.width / 2;
    const centerY = this.config.height / 2;

    this.ctx.clearRect(0, 0, this.config.width, this.config.height);

    // Calculate intro progress
    if (this.config.introEnabled && this.introPhase) {
      this.introProgress = Math.min(1, time / this.config.introDuration);
      if (this.introProgress >= 1) {
        this.introPhase = false;
        this.introProgress = 1;
      }
    } else {
      this.introProgress = 1;
    }

    // Rotation builds up during intro, then continues normally
    const baseRotation = this.introPhase ? 0 : (time - this.config.introDuration);
    this.rotationY = baseRotation * this.config.rotationSpeed + (this.introProgress * Math.PI * 0.15);
    this.rotationX = Math.sin((this.introPhase ? time * 0.5 : time) * 0.2) * 0.3 * this.introProgress;

    // Update nodes with intro progress
    this.nodes.forEach(node => node.update(time, this.rotationX, this.rotationY, centerX, centerY, this.introProgress));

    // Sort by depth
    const sortedNodes = [...this.nodes].sort((a, b) => a.z - b.z);

    // Only evolve after intro is complete
    if (!this.introPhase) {
      this._evolveGraph(time);
    }

    // Draw edges with intro fade-in
    const edgeOpacityMult = this.introPhase ? Math.pow(this.introProgress, 2) : 1;
    this.edges.forEach(edge => {
      const opacity = edge.update(time) * edgeOpacityMult;
      this._drawEdge(edge, opacity);
    });

    // Draw nodes
    sortedNodes.forEach(node => this._drawNode(node, time));

    this.animationId = requestAnimationFrame(this._animate);
  }

  // Public API
  show(text) {
    if (text && this.textEl) {
      this.textEl.textContent = text;
    }
    this.wrapper.classList.add('active');
    this.isVisible = true;
    this.startTime = null;
    
    // Reset intro animation
    this.introPhase = this.config.introEnabled;
    this.introProgress = 0;
    this.rotationX = 0;
    this.rotationY = 0;
    
    // Reinitialize nodes to reset their positions
    this._initializeGraph();
    
    this._animate(performance.now());
  }

  hide(immediate = false) {
    if (immediate) {
      this.wrapper.classList.remove('active', 'fade-out');
      this.isVisible = false;
      if (this.animationId) {
        cancelAnimationFrame(this.animationId);
        this.animationId = null;
      }
    } else {
      // Smooth fade out
      this.wrapper.classList.add('fade-out');
      setTimeout(() => {
        this.wrapper.classList.remove('active', 'fade-out');
        this.isVisible = false;
        if (this.animationId) {
          cancelAnimationFrame(this.animationId);
          this.animationId = null;
        }
      }, 400); // Match CSS transition duration
    }
  }

  setText(text) {
    if (this.textEl) {
      this.textEl.textContent = text;
    }
  }

  destroy() {
    this.hide();
    this.wrapper.remove();
  }

  // Static methods for overlay usage
  static showOverlay(text = 'Loading', options = {}) {
    if (GraphLoader.overlayInstance) {
      GraphLoader.overlayInstance.show(text);
      return GraphLoader.overlayInstance;
    }

    const overlay = document.createElement('div');
    overlay.id = 'graph-loader-overlay';
    overlay.className = 'graph-loader-overlay';
    document.body.appendChild(overlay);

    GraphLoader.overlayInstance = new GraphLoader(overlay, {
      width: 250,
      height: 250,
      text,
      ...options
    });
    
    // Add overlay class to wrapper
    GraphLoader.overlayInstance.wrapper.classList.add('graph-loader-overlay');
    GraphLoader.overlayInstance.show(text);
    
    return GraphLoader.overlayInstance;
  }

  static hideOverlay() {
    if (GraphLoader.overlayInstance) {
      GraphLoader.overlayInstance.destroy();
      const overlay = document.getElementById('graph-loader-overlay');
      if (overlay) overlay.remove();
      GraphLoader.overlayInstance = null;
    }
  }

  static setOverlayText(text) {
    if (GraphLoader.overlayInstance) {
      GraphLoader.overlayInstance.setText(text);
    }
  }
}

// Node class
class GraphLoaderNode {
  constructor(index, total, baseRadius) {
    this.index = index;
    this.total = total;
    this.baseRadius = baseRadius;
    
    // Target sphere position (fibonacci sphere distribution)
    this.baseTheta = (index / total) * Math.PI * 2;
    this.basePhi = Math.acos(1 - 2 * (index + 0.5) / total);
    this.theta = this.baseTheta;
    this.phi = this.basePhi;
    this.radius = baseRadius;
    
    // Calculate target sphere position
    this.targetX = baseRadius * Math.sin(this.basePhi) * Math.cos(this.baseTheta);
    this.targetY = baseRadius * Math.sin(this.basePhi) * Math.sin(this.baseTheta);
    this.targetZ = baseRadius * Math.cos(this.basePhi);
    
    // Initial V-shape position
    this._calculateVPosition();
    
    // Current interpolated position
    this.x = this.startX;
    this.y = this.startY;
    this.z = this.startZ;
    
    // Animation properties
    this.pulseOffset = Math.random() * Math.PI * 2;
    this.driftSpeed = 0.5 + Math.random() * 0.5;
    this.driftAmount = 10 + Math.random() * 15;
    this.screenX = 0;
    this.screenY = 0;
    this.scale = 1;
    
    // Staggered unfurl - nodes unfurl at different times
    this.unfurlDelay = (index / total) * 0.4; // 0 to 0.4 seconds stagger
  }

  _calculateVPosition() {
    // Create a V shape - nodes distributed along two angled lines meeting at TOP
    // V shape: tip at top, arms spread downward and outward
    const half = Math.floor(this.total / 2);
    const isLeftSide = this.index < half;
    const sideIndex = isLeftSide ? this.index : this.index - half;
    const sideTotal = isLeftSide ? half : this.total - half;
    
    // V parameters
    const vHeight = this.baseRadius * 1.5;
    const vWidth = this.baseRadius * 1.2;
    const vDepth = this.baseRadius * 0.3;
    
    // Progress along the V arm (0 = tip at top, 1 = bottom of arms)
    const t = sideTotal > 1 ? sideIndex / (sideTotal - 1) : 0;
    
    // Calculate position on V - tip at top, spreading down
    this.startY = -vHeight * 0.5 + t * vHeight; // Start at top, go down
    this.startX = isLeftSide ? -t * vWidth : t * vWidth; // Spread outward as we go down
    this.startZ = (Math.random() - 0.5) * vDepth; // Slight depth variation
    
    // Flip Y to put tip at top (negate Y axis)
    this.startY = -this.startY;
    
    // Add slight randomness to make it organic
    this.startX += (Math.random() - 0.5) * 8;
    this.startY += (Math.random() - 0.5) * 8;
  }

  update(time, rotationX, rotationY, centerX, centerY, introProgress = 1) {
    // Easing function for smooth unfurl
    const easeOutBack = (t) => {
      const c1 = 1.70158;
      const c3 = c1 + 1;
      return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
    };
    
    const easeInOutCubic = (t) => {
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    };

    // Calculate this node's individual progress with stagger
    let nodeProgress = introProgress;
    if (introProgress < 1) {
      // Adjust for staggered start
      const adjustedProgress = Math.max(0, (introProgress - this.unfurlDelay) / (1 - this.unfurlDelay));
      nodeProgress = easeOutBack(Math.min(1, adjustedProgress));
    }

    // Base position - interpolate from V to sphere
    let baseX, baseY, baseZ;
    
    if (nodeProgress < 1) {
      // Interpolating from V to sphere
      baseX = this.startX + (this.targetX - this.startX) * nodeProgress;
      baseY = this.startY + (this.targetY - this.startY) * nodeProgress;
      baseZ = this.startZ + (this.targetZ - this.startZ) * nodeProgress;
    } else {
      // Normal sphere position with drift
      const drift = Math.sin(time * this.driftSpeed + this.pulseOffset) * this.driftAmount;
      const currentRadius = this.baseRadius + drift;
      
      baseX = currentRadius * Math.sin(this.phi) * Math.cos(this.theta);
      baseY = currentRadius * Math.sin(this.phi) * Math.sin(this.theta);
      baseZ = currentRadius * Math.cos(this.phi);
    }

    this.x = baseX;
    this.y = baseY;
    this.z = baseZ;

    // Apply rotation - gradually increase rotation during intro
    const rotationMult = introProgress < 1 ? easeInOutCubic(introProgress) : 1;
    const activeRotationY = rotationY * rotationMult;
    const activeRotationX = rotationX * rotationMult;

    // Rotate Y
    let tempX = this.x * Math.cos(activeRotationY) - this.z * Math.sin(activeRotationY);
    let tempZ = this.x * Math.sin(activeRotationY) + this.z * Math.cos(activeRotationY);
    this.x = tempX;
    this.z = tempZ;

    // Rotate X
    let tempY = this.y * Math.cos(activeRotationX) - this.z * Math.sin(activeRotationX);
    tempZ = this.y * Math.sin(activeRotationX) + this.z * Math.cos(activeRotationX);
    this.y = tempY;
    this.z = tempZ;

    // Project to 2D
    const perspective = 400;
    const fov = perspective / (perspective + this.z);
    this.screenX = centerX + this.x * fov;
    this.screenY = centerY + this.y * fov;
    this.scale = fov;
  }
}

// Edge class
class GraphLoaderEdge {
  constructor(nodeA, nodeB) {
    this.nodeA = nodeA;
    this.nodeB = nodeB;
    this.life = 0;
    this.growing = true;
    this.pulsePhase = Math.random() * Math.PI * 2;
    this.fadeSpeed = 0.002 + Math.random() * 0.003;
  }

  update(time) {
    const pulse = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(time * 2 + this.pulsePhase));
    
    if (this.growing) {
      this.life = Math.min(1, this.life + this.fadeSpeed * 2);
      if (this.life >= 1) this.growing = false;
    }
    
    return this.life * pulse;
  }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GraphLoader;
}

// Auto-register if VeraChat exists
if (typeof VeraChat !== 'undefined') {
  VeraChat.prototype.GraphLoader = GraphLoader;
}

// Manual control available via:
// javascript// Show/hide programmatically
// window.graphLoaderUtils.show('Custom message');
// window.graphLoaderUtils.hide();

// // Or via VeraChat instance
// app.showGraphLoader('Loading...');
// app.hideGraphLoader();

// // Clear graph and show loader
// clearGraph();  // Shows "Graph cleared"

// New helper methods added:
// javascript// Refresh graph with loading animation
// app.reloadGraph();

// // Clear graph (shows loader)
// app.clearGraph();

// // Add nodes incrementally (shows loader if graph was empty)
// app.addNodesToGraph(newNodes, newEdges);

// // Manual control
// window.graphLoaderUtils.show('Custom message');
// window.graphLoaderUtils.hide(true);  // force hide
// window.graphLoaderUtils.checkState(networkData);  // auto show/hide based on data