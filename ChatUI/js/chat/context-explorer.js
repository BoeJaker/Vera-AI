// =====================================================================
// Vera Memory Graph Explorer v6.0 — Frame Timeline
// • All v5.1 features preserved
// • Frame system: per-message context snapshots stored and browsable
// • Timeline scrubber bar with frame thumbnails and Q-text previews
// • "Full session view" mode: all frames composited, nodes colour-coded
//   by which frame(s) they appeared in, edges show temporal flow
// • Frame diff mode: highlight nodes added/dropped vs previous frame
// • Auto-captures every time new context arrives (WS complete / CI refresh)
// • Manual capture button
// =====================================================================
(() => {

const API_BASE = 'http://llm.int:8888';

// ─── Source classification helpers ────────────────────────────────────
function nodeLayer(n) {
    const GRAPH_SOURCES = new Set([
        'graph','expanded','graph_traverse','graph_rerank',
        'focus','keyword_neo4j','entity_recall','neighbour_swap',
        'chunk_reassembled','recalled_exchange',
    ]);
    const GRAPH_TYPES = new Set(['entity','extracted_entity','focus']);
    const VEC_SOURCES = new Set(['vector_session','vector_xsession','vector_longterm']);
    const VEC_TYPES   = new Set(['query','response','recalled_exchange']);
    const fromGraph = GRAPH_SOURCES.has(n.source)||GRAPH_TYPES.has(n.type)||n.graph_score>0.05;
    const fromVec   = VEC_SOURCES.has(n.source)||VEC_TYPES.has(n.type)||n.vector_score>0.05;
    if (fromGraph&&fromVec) return 'both';
    if (fromGraph) return 'graph';
    if (fromVec)   return 'vector';
    return 'both';
}
function isGraphSub(n) {
    return new Set(['graph_traverse','keyword_neo4j','entity_recall',
        'neighbour_swap','chunk_reassembled','recalled_exchange','graph_rerank']).has(n.source);
}
function nodeVisible(n) {
    // History and focus nodes are always visible — they provide structural context
    // regardless of which retrieval mode is active
    if (n.source==='history'||n.source==='focus') return true;
    if (MG.mode==='blend') return true;
    const layer=nodeLayer(n);
    if (layer==='both') return true;
    if (MG.mode==='semantic') return layer==='vector';
    if (MG.mode==='graph')   return layer==='graph';
    return true;
}

// ─── Frame helpers ────────────────────────────────────────────────────
function makeFrameId() { return `f${Date.now()}_${Math.random().toString(36).slice(2,7)}`; }

/** Extract short query label from raw context data */
function frameLabel(rawData, idx) {
    const q = rawData?._query || '';
    if (q) return q.length > 48 ? q.slice(0, 48) + '…' : q;
    return `Frame ${idx + 1}`;
}

/** Serialise current nodes/edges into a lightweight snapshot */
function snapshotNodes(nodesMap) {
    const out = [];
    for (const n of nodesMap.values()) {
        out.push({
            id: n.id, text: n.text, type: n.type,
            score: n.score, vector_score: n.vector_score,
            graph_score: n.graph_score, keyword_score: n.keyword_score,
            source: n.source, metadata: n.metadata,
        });
    }
    return out;
}

function snapshotEdges(edges) {
    return edges.map(e => ({ from: e.from, to: e.to, type: e.type, weight: e.weight, label: e.label }));
}

// ─── State ────────────────────────────────────────────────────────────
const MG = {
    open: false, canvas: null, ctx: null, animFrame: null,
    W: 0, H: 0,
    mode: 'blend', showSemantic: true, showGraph: true,
    nodeLimit: 50, focusThreshold: 0.15,
    nodes: new Map(), edges: [],
    loading: false, currentQuery: '', sessionId: '',
    dragging: null, hovered: null, selected: null,
    pan: { x: 0, y: 0 }, zoom: 1, isPanning: false,
    simRunning: false, tick: 0,
    theme: null,
    expandPanel: null,
    injectedContext: new Map(),

    // ── Frame system ──────────────────────────────────────────────────
    frames: [],          // Array<Frame>
    activeFrameIdx: -1,  // -1 = live / session view
    sessionView: false,  // true = show all frames composited
    diffMode: false,     // true = highlight delta vs prev frame
    frameBarOpen: true,
    _pendingRawData: null,

    // ── Context visibility ─────────────────────────────────────────────
    // Set of node IDs that are actively IN context for the current frame.
    // Nodes not in this set but present in the graph are "retrieved but out-of-context".
    inContextIds: new Set(),
    // Whether we're in a live-typing preview (context is speculative)
    livePreview: false,
};

// Frame schema:
// { id, idx, label, query, ts, nodeSnap:[], edgeSnap:[], nodeCount, sessionId }

// ─── Default visual config ────────────────────────────────────────────
let NS = buildNS(null);
let ES = buildES(null);
let COLORS = buildColors(null);

// ── Palette for frame colouring in session view ───────────────────────
const FRAME_PALETTE = [
    '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
    '#06b6d4','#f472b6','#84cc16','#fb923c','#a78bfa',
    '#22d3ee','#fbbf24','#4ade80','#f87171','#60a5fa',
];
function frameColor(idx) { return FRAME_PALETTE[idx % FRAME_PALETTE.length]; }

// ─── Theme integration ────────────────────────────────────────────────
function buildNS(pf) {
    const c = pf || {};
    return {
        query:             { color: c.accentResponse   || '#3b82f6', r:10, g:'Q' },
        response:          { color: c.accentThought    || '#8b5cf6', r:10, g:'R' },
        entity:            { color: c.accentSuccess    || '#10b981', r: 8, g:'E' },
        extracted_entity:  { color: c.accentTool       || '#06b6d4', r: 7, g:'X' },
        document:          { color: c.accentFlowchart  || '#f59e0b', r: 9, g:'D' },
        focus:             { color: c.accentWarning    || '#fbbf24', r:13, g:'★' },
        recalled_exchange: { color: c.accentThought    || '#a78bfa', r:10, g:'M' },
        history:           { color: c.textSecondary    || '#64748b', r: 8, g:'H' },
        keyword_neo4j:     { color: '#06b6d4',                       r: 8, g:'K' },
        entity_recall:     { color: '#34d399',                       r: 7, g:'↳' },
        neighbour_swap:    { color: '#a78bfa',                       r: 7, g:'⇄' },
        chunk_reassembled: { color: '#f59e0b',                       r: 9, g:'▦' },
        default:           { color: c.text             || '#475569', r: 7, g:'·' },
    };
}
function buildES(pf) {
    const c = pf || {};
    return {
        semantic:{ color: c.accentResponse  || '#3b82f6', w:1,   dash:[5,4], a:0.4  },
        graph:   { color: c.accentSuccess   || '#10b981', w:1.5, dash:[],    a:0.55 },
        follows: { color: c.accentThought   || '#8b5cf6', w:2,   dash:[],    a:0.65 },
        pair:    { color: c.accentThought   || '#a78bfa', w:1,   dash:[3,3], a:0.5  },
        temporal:{ color: '#475569',                      w:1,   dash:[2,4], a:0.3  },
    };
}
function buildColors(pf) {
    const c = pf || {};
    return {
        bg:         c.bg           || '#07111e',
        grid:       c.borderSubtle || '#0c1d30',
        hudText:    c.borderSubtle || '#1a3050',
        hudLoading: c.accentStage  || '#3b82f6',
        emptyText:  c.borderSubtle || '#1a3050',
        labelBg:    c.bg           || '#07111e',
    };
}

function applyTheme() {
    const tm = window.themeManager;
    if (!tm) return;
    const config = tm.getThemeConfig(tm.getCurrentTheme()||'default');
    if (!config) return;
    const pf = config.proactiveFocus || null;
    MG.theme = pf; NS = buildNS(pf); ES = buildES(pf); COLORS = buildColors(pf);
    _syncDOMTheme(config);
    updateAlpha();
    if (!MG.simRunning) simReheat(0.3); // gentle nudge to re-render after theme change
}

function _syncDOMTheme(config) {
    const pf  = config.proactiveFocus || {};
    const vars = config.variables     || {};
    let el = document.getElementById('mg-theme-vars');
    if (!el) { el=document.createElement('style'); el.id='mg-theme-vars'; document.head.appendChild(el); }
    const bg         = pf.bg          || vars['--bg']            || '#07111e';
    const bgPanel    = pf.bgPanel     || vars['--panel-bg']      || '#0b1929';
    const bgPanelHdr = pf.bgPanelHdr  || vars['--bg-surface']    || '#0b1929';
    const border     = pf.border      || vars['--border']         || '#152236';
    const text       = pf.text        || vars['--text-secondary'] || '#334155';
    const accent     = pf.accentStage || vars['--accent']         || '#3b82f6';
    const success    = pf.accentSuccess|| '#10b981';
    el.textContent = `
        #mg-win{background:${bg}!important;border-color:${border}!important;box-shadow:0 0 0 1px ${accent}0f,0 28px 70px rgba(0,0,0,.75)!important;}
        #mg-bar{background:${bgPanelHdr}!important;border-bottom-color:${border}!important;}
        .mg-logo{color:${accent}!important;}
        .mg-mb{border-color:${border}!important;color:${text}!important;}
        .mg-mb:hover{border-color:${pf.accentStage||border}!important;color:${pf.textSecondary||text}!important;}
        .mg-on{background:${accent}1a!important;border-color:${accent}66!important;color:${accent}!important;}
        #mg-ctrls .mg-lbl{color:${text}!important;}
        #mg-ctrls .mg-lbl span{color:${accent}!important;}
        .mg-btn{border-color:${border}!important;color:${text}!important;background:transparent!important;}
        #mg-wrap{background:radial-gradient(ellipse at 35% 40%,${bgPanel} 0%,${bg} 100%)!important;}
        #mg-leg{background:${bgPanelHdr}!important;border-top-color:${border}!important;}
        .mg-li{color:${text}!important;}
        .mg-sep{background:${border}!important;}
        #mg-hint{color:${pf.borderSubtle||'#0c1d30'}!important;}
        .mg-detail{background:${bgPanel}!important;border-color:${pf.runBorder||border}!important;}
        .mg-da-btn{border-color:${border}!important;color:${accent}!important;}
        .mg-da-btn:hover{background:${accent}1a!important;border-color:${accent}66!important;}
        #mg-expand{background:${bgPanel};border:1px solid ${pf.runBorder||border};}
        #mg-expand .mg-ep-hdr{background:${bgPanelHdr};border-bottom:1px solid ${border};color:${accent};}
        #mg-expand .mg-ep-item{border-bottom:1px solid ${border}22;color:${text};}
        #mg-expand .mg-ep-item:hover{background:${accent}0a;}
        #mg-expand .mg-ep-item.checked{background:${accent}14;}
        #mg-expand .mg-ep-score{color:${accent};}
        #mg-expand .mg-ep-type{color:${pf.textSecondary||text};}
        #mg-expand .mg-ep-text{color:${pf.responseText||'#e2e8f0'};}
        #mg-expand .mg-ep-footer{background:${bgPanelHdr};border-top:1px solid ${border};}
        #mg-expand .mg-ep-add-btn{background:${success};color:#fff;}
        #mg-expand .mg-ep-inject-btn{background:${accent};color:#fff;}
        #mg-expand .mg-ep-cancel{border-color:${border};color:${text};}
        #mg-ctx-tray{background:${bgPanelHdr};border:1px solid ${success}44;}
        #mg-ctx-tray .mg-ct-label{color:${success};}
        #mg-ctx-tray .mg-ct-chip{background:${success}18;border:1px solid ${success}44;color:${pf.responseText||'#e2e8f0'};}
        #mg-ctx-tray .mg-ct-send-btn{background:${success};color:#fff;}
        #mg-ctx-tray .mg-ct-clear{color:${text};border-color:${border};}
        #mg-frame-bar{background:${bgPanelHdr};border-top:1px solid ${border};}
        .mg-frame-thumb{border-color:${border};background:${bg};}
        .mg-frame-thumb:hover{border-color:${accent}55;}
        .mg-frame-thumb.active{border-color:${accent}!important;box-shadow:0 0 0 1px ${accent}44;}
        .mg-frame-thumb.session-active{border-color:#f59e0b!important;box-shadow:0 0 0 1px #f59e0b44;}
        #mg-frame-scrubber{accent-color:${accent};}
        .mg-frame-meta{color:${text};}
        .mg-fbar-btn{border-color:${border};color:${text};}
        .mg-fbar-btn:hover{border-color:${accent}55;color:${accent};}
        .mg-fbar-btn.mg-on{background:${accent}1a;border-color:${accent}66;color:${accent};}
    `;
}

// ─── Node ─────────────────────────────────────────────────────────────
class GNode {
    constructor(id, d) {
        this.id            = id;
        this.text          = String(d.text || id);
        this.type          = (d.type||'default').toLowerCase().replace(/\s+/g,'_');
        this.score         = +d.score        || 0.5;
        this.vector_score  = +d.vector_score || 0;
        this.graph_score   = +d.graph_score  || 0;
        this.keyword_score = +d.keyword_score|| 0;
        this.source        = d.source || '';
        this.metadata      = d.metadata || {};
        const a=Math.random()*Math.PI*2, dist=80+Math.random()*160;
        this.x=Math.cos(a)*dist; this.y=Math.sin(a)*dist;
        this.vx=0; this.vy=0; this.fx=null; this.fy=null;
        this.alpha=0; this.tAlpha=1;
        this.pulse=Math.random()*Math.PI*2;
        // Frame membership (set during session view)
        this.frameSet = new Set(); // Set<frameIdx>
    }
    get ns() {
        const srcNS={ keyword_neo4j:NS.keyword_neo4j, entity_recall:NS.entity_recall,
            neighbour_swap:NS.neighbour_swap, chunk_reassembled:NS.chunk_reassembled }[this.source];
        return srcNS||NS[this.type]||NS.default;
    }
    get r()   { return this.ns.r+this.score*4; }
    get rel() {
        if (MG.mode==='semantic') return this.vector_score||this.score;
        if (MG.mode==='graph')   return this.graph_score||this.score;
        return this.score;
    }
    get graphSub() { return isGraphSub(this); }
    // true = this node is actively in the LLM's context window for this frame
    get inContext() { return MG.inContextIds.has(this.id); }
    get ghost() {
        if (!nodeVisible(this)) return true;
        // Only ghost by threshold when threshold > 0
        if (MG.focusThreshold > 0 && this.rel < MG.focusThreshold
            && this !== MG.selected && this !== MG.hovered) return true;
        return false;
    }
    get hidden() { return !nodeVisible(this)&&this!==MG.selected&&this!==MG.hovered; }
    get hot()    { return this===MG.selected||this===MG.hovered; }
    /** Primary colour in session view — blended from frame colours if multi-frame */
    get sessionColor() {
        const idxs = [...this.frameSet];
        if (!idxs.length) return this.ns.color;
        if (idxs.length===1) return frameColor(idxs[0]);
        // Blend: just use the first two with alpha layering hint
        return frameColor(idxs[0]);
    }
}

// ─── Alpha update ──────────────────────────────────────────────────────
function updateAlpha() {
    const hasCtx = MG.inContextIds.size > 0;
    const thresh  = MG.focusThreshold;   // 0 = show everything, 0.5 = ghost below 50%
    for (const n of MG.nodes.values()) {
        if (n.hidden) {
            n.tAlpha = 0;
        } else if (n === MG.selected || n === MG.hovered) {
            // Always fully bright when selected/hovered
            n.tAlpha = 1;
        } else if (hasCtx && !n.inContext && thresh > 0) {
            // Out-of-context dimming only active when threshold > 0
            // Dim to a fixed low value — not invisible, just de-emphasised
            n.tAlpha = Math.max(0.08, Math.min(0.22, n.rel * 0.4));
        } else if (thresh > 0 && n.rel < thresh) {
            // Below focus threshold — ghost
            n.tAlpha = 0.08;
        } else if (n.inContext && hasCtx) {
            // Fully in context — bright
            n.tAlpha = Math.min(1, Math.max(0.75, n.rel + 0.25));
        } else {
            // Normal — scale with relevance, floor at 0.4
            n.tAlpha = Math.min(1, Math.max(0.4, n.rel + 0.15));
        }
    }
}

// ─── Frame capture ────────────────────────────────────────────────────
function captureFrame(rawData) {
    const idx   = MG.frames.length;
    const label = frameLabel(rawData, idx);

    // ── Dedup guard ──────────────────────────────────────────────────────
    // Skip if the *retrieved* node set (excluding history/focus) is >85%
    // identical to the last frame. This prevents duplicate frames when the
    // backend returns the same stable long-term docs across consecutive queries.
    const incomingFp = _frameFp(MG.nodes);
    if (MG.frames.length > 0) {
        const lastFp = MG.frames[MG.frames.length - 1]._fp;
        if (lastFp !== undefined && incomingFp !== '') {
            const sim = _fpSimilarity(lastFp, incomingFp);
            // Only skip truly identical frames (same exact node set)
            // 0.98 allows a single node change through while blocking exact duplicates
            if (sim >= 0.98) {
                console.debug('[MG] captureFrame: identical context — skipping duplicate frame');
                return null;
            }
        }
    }

    // ── Snapshot: exclude history nodes from frame storage ───────────────
    // History grows monotonically (each turn appends the previous exchange),
    // so storing it per-frame would make every frame look like a superset of
    // the previous one. The meaningful diff is in ranked_hits only.
    const filteredNodes = [...MG.nodes.values()]
        .filter(n => n.source !== 'history');
    const filteredEdges = MG.edges.filter(e => {
        const a = MG.nodes.get(e.from);
        const b = MG.nodes.get(e.to);
        return a && b && a.source !== 'history' && b.source !== 'history';
    });

    const frame = {
        id:         makeFrameId(),
        idx,
        label,
        query:      rawData?._query || '',
        ts:         Date.now(),
        // Strip metadata from nodeSnap — can be large/nested, not needed for graph replay
        nodeSnap:   filteredNodes.map(n => ({
            id: n.id, text: (n.text||'').slice(0, 200), type: n.type,
            score: n.score, vector_score: n.vector_score,
            graph_score: n.graph_score, keyword_score: n.keyword_score,
            source: n.source,
        })),
        edgeSnap:   filteredEdges.map(e => ({
            from: e.from, to: e.to, type: e.type, weight: e.weight, label: e.label||'',
        })),
        nodeCount:  filteredNodes.length,
        historyCount: [...MG.nodes.values()].filter(n => n.source === 'history').length,
        sessionId:  rawData?._sessionId || MG.sessionId || '',
        // rawData intentionally NOT stored — too large for localStorage.
        // MG._pendingRawData holds the latest payload if needed.
        rawData:    null,
        _fp:        incomingFp,
        _inContextIds: [...MG.inContextIds],
    };
    MG.frames.push(frame);
    saveFrames();
    renderFrameBar();
    showFrameToast(`Frame ${idx+1} captured — "${label}"`);
    return frame;
}

/**
 * Fingerprint only the *retrieved* context nodes — history and focus nodes
 * grow monotonically and would cause every frame to look unique even when
 * the actual retrieval result is identical.
 * Returns a sorted string of IDs for nodes whose source is NOT 'history'
 * and NOT 'focus'.
 */
function _frameFp(nodesMap) {
    return [...nodesMap.values()]
        .filter(n => n.source !== 'history' && n.source !== 'focus')
        .map(n => n.id)
        .sort()
        .join('|');
}

/** Jaccard similarity between two fingerprint strings (treat as ID sets) */
function _fpSimilarity(fpA, fpB) {
    if (!fpA || !fpB) return 0;  // empty fp = treat as different, never skip
    const a = new Set(fpA.split('|').filter(Boolean));
    const b = new Set(fpB.split('|').filter(Boolean));
    if (a.size === 0 || b.size === 0) return 0;  // empty = different
    let inter = 0;
    for (const id of a) if (b.has(id)) inter++;
    return inter / (a.size + b.size - inter);
}

function showFrameToast(msg) {
    let el=document.getElementById('mg-frame-toast');
    if (!el){ el=document.createElement('div'); el.id='mg-frame-toast'; document.body.appendChild(el); }
    el.textContent=msg; el.style.opacity='1';
    clearTimeout(el._t);
    el._t=setTimeout(()=>{ el.style.opacity='0'; },2200);
}

// ─── Load a frame into the live graph ─────────────────────────────────
function activateFrame(idx) {
    if (idx<0||idx>=MG.frames.length) return;
    MG.activeFrameIdx=idx;
    MG.sessionView=false;
    MG.livePreview=false;
    const f=MG.frames[idx];
    // Restore inContextIds — prefer stored _inContextIds (works after localStorage restore
    // where rawData is null)
    MG.inContextIds=new Set();
    const _ici = f._inContextIds || [];
    if (_ici.length) {
        _ici.forEach(id => MG.inContextIds.add(id));
    } else {
        for (const h of (f.rawData?.vectors?.ranked_hits||[])) {
            const hid=h.id||h.metadata?.node_id; if(hid) MG.inContextIds.add(hid);
        }
    }
    // Clear and rebuild
    MG.nodes.clear(); MG.edges=[];
    for (const d of f.nodeSnap) {
        const n=new GNode(d.id,d);
        MG.nodes.set(d.id,n);
    }
    for (const e of f.edgeSnap) {
        MG.edges.push({...e, alpha:0});
    }
    updateAlpha();
    simReheat(0.8);
    MG.selected=null; MG.hovered=null;
    hideDetail();
    renderFrameBar();
    _updateScrubber();
}

// ─── Session view: composite ALL frames ───────────────────────────────
function activateSessionView() {
    if (!MG.frames.length) return;
    MG.sessionView=true;
    MG.activeFrameIdx=-1;
    MG.nodes.clear(); MG.edges=[];
    const edgeSig=new Set();

    for (let fi=0;fi<MG.frames.length;fi++) {
        const f=MG.frames[fi];
        for (const d of f.nodeSnap) {
            if (!MG.nodes.has(d.id)) {
                const n=new GNode(d.id,d);
                MG.nodes.set(d.id,n);
            }
            MG.nodes.get(d.id).frameSet.add(fi);
        }
        for (const e of f.edgeSnap) {
            const sig=`${e.from}→${e.to}:${e.type}`;
            if (!edgeSig.has(sig)) {
                edgeSig.add(sig);
                MG.edges.push({...e,alpha:0});
            }
        }
        // Add temporal edges between consecutive frames (shared nodes)
        if (fi>0) {
            const prev=MG.frames[fi-1];
            const prevIds=new Set(prev.nodeSnap.map(n=>n.id));
            for (const d of f.nodeSnap) {
                if (prevIds.has(d.id)) {
                    const sig=`${d.id}⟳temporal${fi}`;
                    if (!edgeSig.has(sig)) {
                        edgeSig.add(sig);
                        MG.edges.push({from:d.id,to:d.id,type:'temporal',weight:0.3,label:`f${fi}`,alpha:0,_temporal:true,_fi:fi});
                    }
                }
            }
        }
    }

    updateAlpha();
    simReheat();
    MG.selected=null; MG.hovered=null;
    hideDetail();
    renderFrameBar();
    _updateScrubber();
}

// ─── Live view: restore from last frame or clear ───────────────────────
function activateLiveView() {
    MG.activeFrameIdx=-1;
    MG.sessionView=false;
    // If there's a last frame, restore it, but keep live label
    if (MG.frames.length>0) activateFrame(MG.frames.length-1);
    renderFrameBar();
}

// ─── Diff overlay: mark nodes added/removed vs prev frame ─────────────
function computeDiff(frameIdx) {
    if (frameIdx<=0||frameIdx>=MG.frames.length) return {added:new Set(),removed:new Set()};
    const curr=new Set(MG.frames[frameIdx].nodeSnap.map(n=>n.id));
    const prev=new Set(MG.frames[frameIdx-1].nodeSnap.map(n=>n.id));
    const added=new Set([...curr].filter(id=>!prev.has(id)));
    const removed=new Set([...prev].filter(id=>!curr.has(id)));
    return {added,removed};
}

// ─── Ingest ────────────────────────────────────────────────────────────
function ingestContext(raw, isCommit=false) {
    if (!raw) return;
    MG._pendingRawData=raw;
    const data=normalise(raw);
    const seenQ=new Set();
    const queue=[];

    function push(id,d) {
        if (!id||!d.text||seenQ.has(id)) return;
        seenQ.add(id); queue.push({id,d});
    }

    for (const h of data.ranked) {
        const id=h.id||h.metadata?.node_id||h.metadata?.id||`rh_${hash(h.text)}`;
        push(id,{text:h.text,type:h.metadata?.type||srcType(h.source),
            score:h.score??0.5,vector_score:h.vector_score??0,
            graph_score:h.graph_score??0,keyword_score:h.keyword_score??0,
            source:h.source||'',metadata:h.metadata||{}});
    }
    for (const h of data.session) {
        const id=h.id||`sh_${hash(h.text)}`;
        const sc=h.score??1-(h.distance??0.5);
        push(id,{text:h.text,type:h.metadata?.type||'query',score:sc,vector_score:sc,
            graph_score:0,keyword_score:0,source:'vector_session',metadata:h.metadata||{}});
    }
    for (const h of data.longterm) {
        const id=h.id||`lt_${hash(h.text)}`;
        const sc=h.score??1-(h.distance??0.5);
        push(id,{text:h.text,type:h.metadata?.type||'document',score:sc,vector_score:sc,
            graph_score:0,keyword_score:0,source:'vector_longterm',metadata:h.metadata||{}});
    }
    for (const e of data.entities) {
        const id=e.id||`ent_${hash(e.text)}`;
        push(id,{text:e.text,type:(e.label||'entity').toLowerCase().replace(/\s+/g,'_'),
            score:e.confidence??0.5,vector_score:0,graph_score:e.confidence??0.5,
            keyword_score:0,source:'graph',metadata:{}});
    }
    for (const f of data.focus) {
        const id=`foc_${hash(f)}`;
        push(id,{text:f,type:'focus',score:1,vector_score:0.5,graph_score:1,keyword_score:0,source:'focus',metadata:{}});
    }
    const histIds=[];
    for (let i=0;i<data.history.length;i++) {
        const h=data.history[i];
        if (!h.text) continue;
        // Use node_id from metadata if available, otherwise pure content hash
        // (NOT position-indexed, so the same exchange has the same ID across frames)
        const id=h.metadata?.node_id||`hist_${hash(h.text)}`;
        const sc=0.3+(i/Math.max(data.history.length,1))*0.35;
        const role=(h.role||'').toLowerCase();
        push(id,{text:h.text,type:role==='user'||role==='query'?'query':'response',
            score:sc,vector_score:sc,graph_score:0,keyword_score:0,source:'history',metadata:h.metadata||{}});
        histIds.push(id);
    }

    if (queue.length===0) { console.warn('[MG] ingestContext: nothing to render'); return; }
    queue.sort((a,b)=>b.d.score-a.d.score);
    const batch=queue.slice(0, MG.nodeLimit);

    // Return to live mode if browsing a frame or session view
    if (MG.sessionView||MG.activeFrameIdx>=0) {
        MG.sessionView=false;
        MG.activeFrameIdx=-1;
    }

    // ── Snapshot positions of surviving nodes so layout doesn't thrash ──
    const prevPositions = new Map();
    for (const [id, n] of MG.nodes) {
        prevPositions.set(id, { x: n.x, y: n.y, vx: n.vx, vy: n.vy, fx: n.fx, fy: n.fy });
    }

    // ── Determine which nodes are pinned (user-pinned should survive eviction) ──
    const pinned = new Map();
    for (const [id, n] of MG.nodes) {
        if (n.fx !== null) pinned.set(id, n); // pinned node — preserve across frames
    }

    // ── Full replacement: clear everything not in this batch ──
    const incomingIds = new Set(batch.map(({id}) => id));

    // Keep pinned nodes not in batch (user explicitly pinned them)
    MG.nodes.clear();
    for (const [id, n] of pinned) {
        if (!incomingIds.has(id)) MG.nodes.set(id, n);
    }

    // Build new node set from this batch only
    for (const {id, d} of batch) {
        if (MG.nodes.has(id)) {
            // Update score on pinned survivor
            MG.nodes.get(id).score = d.score;
            continue;
        }
        const n = new GNode(id, d);
        // Reuse previous position if this node existed before (smooth transition)
        const prev = prevPositions.get(id);
        if (prev) {
            n.x = prev.x; n.y = prev.y;
            n.vx = prev.vx * 0.5; n.vy = prev.vy * 0.5; // dampen velocity
            n.fx = prev.fx; n.fy = prev.fy;
            n.alpha = 0.6; // already partially visible — skip fade-in flash
        }
        MG.nodes.set(id, n);
    }

    // ── Clear edges — rebuild fresh for this batch ──
    MG.edges = [];

    // ── Compute in-context set: ranked_hits are what the LLM will actually see ──
    MG.inContextIds = new Set();
    const _rankedHits = raw.vectors?.ranked_hits || [];
    for (const h of _rankedHits) {
        const _id = h.id || h.metadata?.node_id || h.metadata?.id;
        if (_id) MG.inContextIds.add(_id);
    }
    for (const _f of (raw.graph?.focus_entities || [])) {
        MG.inContextIds.add('foc_' + hash(_f));
    }

    setTimeout(()=>{
        buildEdges(raw, histIds);
        buildSemanticEdges();
        updateAlpha();
        simReheat(1.0);
        // Capture frame after sim has settled
        if (isCommit) setTimeout(()=>captureFrame(raw), 900);
    }, 30);
}

function normalise(raw) {
    return {
        ranked:   raw.vectors?.ranked_hits   || [],
        session:  raw.vectors?.session_hits  || [],
        longterm: raw.vectors?.longterm_hits || [],
        entities: raw.graph?.entities        || [],
        focus:    raw.graph?.focus_entities  || [],
        history:  raw.history                || [],
    };
}

function buildEdges(raw,histIds) {
    for (let i=0;i<histIds.length-1;i++) addEdge(histIds[i],histIds[i+1],'follows',0.8);
    const allHits=[...(raw.vectors?.ranked_hits||[]),...(raw.vectors?.session_hits||[]),...(raw.vectors?.longterm_hits||[])];
    for (const h of allHits) {
        if (!h.metadata?.pair_promoted||!h.metadata?.pair_of) continue;
        const hid=h.id||h.metadata?.node_id||`rh_${hash(h.text||'')}`;
        addEdge(h.metadata.pair_of,hid,'pair',0.85);
    }
    for (const r of raw.graph?.relations||[]) {
        const fi=r.head_id||`ent_${hash(r.head||'')}`;
        const ti=r.tail_id||`ent_${hash(r.tail||'')}`;
        addEdge(fi,ti,'graph',0.7,r.relation||r.rel||'');
    }
    for (const h of (raw.vectors?.ranked_hits||[])) {
        if (!isGraphSubSource(h.source)) continue;
        const hid=h.id||h.metadata?.node_id||`rh_${hash(h.text||'')}`;
        const pairedOf=h.metadata?.pair_of||h.metadata?.node_id;
        if (pairedOf&&pairedOf!==hid) addEdge(pairedOf,hid,'graph',0.6,h.source||'');
    }
}
function isGraphSubSource(source) {
    return ['graph_traverse','keyword_neo4j','entity_recall','neighbour_swap',
            'chunk_reassembled','recalled_exchange','graph_rerank'].includes(source);
}
function buildSemanticEdges() {
    const nodes=[...MG.nodes.values()].filter(n=>n.score>0.35);
    for (let i=0;i<nodes.length;i++) {
        for (let j=i+1;j<nodes.length;j++) {
            const sim=textSim(nodes[i].text,nodes[j].text);
            if (sim>0.55) addEdge(nodes[i].id,nodes[j].id,'semantic',sim);
        }
    }
}
function addEdge(from,to,type,weight=0.5,label='') {
    if (!from||!to||from===to) return;
    if (MG.edges.find(e=>((e.from===from&&e.to===to)||(e.from===to&&e.to===from))&&e.type===type)) return;
    MG.edges.push({from,to,type,weight,label,alpha:0});
}

// ─── Physics ───────────────────────────────────────────────────────────
// Smooth force-directed layout with alpha-cooling schedule.
const SIM = {
    REPULSE:     1800,   // charge strength
    REST_LEN:    120,    // spring rest length px
    SPRING_K:    0.022,  // spring stiffness
    DAMPING:     0.72,   // velocity damping — lower = more friction, less oscillation
    GRAVITY:     0.002,  // gentle centre-pull
    MIN_DIST:    28,     // clamp prevents explosive repulsion on overlap
    ALPHA:       1.0,    // simulation temperature (mutable)
    ALPHA_DECAY: 0.003,  // cool slowly — 0.003 gives ~230 ticks at 60fps (~4s) to reach 0.5
    ALPHA_MIN:   0.0005, // stop only when very well settled
};

function simStep() {
    if (!MG.simRunning) return;
    MG.tick++;
    SIM.ALPHA = Math.max(SIM.ALPHA_MIN, SIM.ALPHA * (1 - SIM.ALPHA_DECAY));
    if (SIM.ALPHA <= SIM.ALPHA_MIN) { MG.simRunning = false; return; }

    const alpha = SIM.ALPHA;
    const nodes = [...MG.nodes.values()].filter(n=>!n.hidden);
    for (const n of nodes) { n.ax=0; n.ay=0; }

    // Charge repulsion
    for (let i=0;i<nodes.length;i++) {
        for (let j=i+1;j<nodes.length;j++) {
            const a=nodes[i], b=nodes[j];
            let dx=b.x-a.x, dy=b.y-a.y;
            let d2=dx*dx+dy*dy;
            if (d2 < SIM.MIN_DIST*SIM.MIN_DIST) {
                dx += (Math.random()-.5)*4; dy += (Math.random()-.5)*4;
                d2 = dx*dx+dy*dy||1;
            }
            const d=Math.sqrt(d2);
            const f=(SIM.REPULSE/d2)*alpha;
            a.ax-=(dx/d)*f; a.ay-=(dy/d)*f;
            b.ax+=(dx/d)*f; b.ay+=(dy/d)*f;
        }
    }

    // Spring attraction
    for (const e of MG.edges) {
        if (e._temporal) continue;
        const a=MG.nodes.get(e.from), b=MG.nodes.get(e.to);
        if (!a||!b||a.hidden||b.hidden) continue;
        const dx=b.x-a.x, dy=b.y-a.y, d=Math.sqrt(dx*dx+dy*dy)||1;
        const f=(d-SIM.REST_LEN)*SIM.SPRING_K*e.weight*alpha;
        if (a.fx===null){a.ax+=(dx/d)*f;a.ay+=(dy/d)*f;}
        if (b.fx===null){b.ax-=(dx/d)*f;b.ay-=(dy/d)*f;}
    }

    // Integrate
    for (const n of nodes) {
        if (n.fx!==null){n.x=n.fx;n.y=n.fy;continue;}
        n.ax+=(-n.x)*SIM.GRAVITY*alpha;
        n.ay+=(-n.y)*SIM.GRAVITY*alpha;
        n.vx=(n.vx+n.ax)*SIM.DAMPING;
        n.vy=(n.vy+n.ay)*SIM.DAMPING;
        n.x+=n.vx; n.y+=n.vy;
    }
}

function simReheat(strength=1.0) { SIM.ALPHA=Math.min(1.0,strength); MG.simRunning=true; }

// ─── Render ────────────────────────────────────────────────────────────
function loop() {
    MG.animFrame=requestAnimationFrame(loop);
    simStep();
    const ctx=MG.ctx; if(!ctx) return;
    const W=MG.W,H=MG.H;
    ctx.clearRect(0,0,W,H);
    drawGrid(ctx,W,H);
    ctx.save();
    ctx.translate(W/2+MG.pan.x,H/2+MG.pan.y);
    ctx.scale(MG.zoom,MG.zoom);
    drawEdges(ctx);
    drawNodes(ctx);
    ctx.restore();
    drawHUD(ctx,W,H);
    for (const n of MG.nodes.values()) n.alpha+=(n.tAlpha-n.alpha)*0.07;
    for (const e of MG.edges) e.alpha+=(1-e.alpha)*0.07;
}

function drawGrid(ctx,W,H) {
    const step=40*MG.zoom;
    const ox=((W/2+MG.pan.x)%step+step)%step;
    const oy=((H/2+MG.pan.y)%step+step)%step;
    ctx.save();ctx.strokeStyle=COLORS.grid;ctx.lineWidth=0.5;
    for(let x=ox-step;x<W+step;x+=step){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(let y=oy-step;y<H+step;y+=step){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
    ctx.restore();
}

function edgeVisible(e) {
    if (e._temporal) return MG.sessionView;
    // follows edges connect history nodes — always visible regardless of mode
    if (e.type==='follows') {
        const a=MG.nodes.get(e.from),b=MG.nodes.get(e.to);
        return !!(a&&b&&!a.hidden&&!b.hidden);
    }
    if (MG.mode==='blend') return true;
    const a=MG.nodes.get(e.from),b=MG.nodes.get(e.to);
    if (!a||!b||a.hidden||b.hidden) return false;
    if (MG.mode==='semantic'&&e.type==='graph') return false;
    if (MG.mode==='graph'&&(e.type==='semantic'||e.type==='pair')) return false;
    return true;
}

function drawEdges(ctx) {
    const t=MG.tick*0.018;
    for (const e of MG.edges) {
        if (!edgeVisible(e)||e.alpha<0.02) continue;
        if (!MG.showSemantic&&(e.type==='semantic'||e.type==='pair')) continue;
        if (!MG.showGraph&&e.type==='graph') continue;  // follows always visible
        const a=MG.nodes.get(e.from),b=MG.nodes.get(e.to);
        if (!a||!b) continue;
        if (e._temporal) continue; // temporal loops drawn separately
        const es=ES[e.type]||ES.graph;
        const hot=a.hot||b.hot;
        const alpha=Math.min(1,es.a*e.alpha*Math.min(a.alpha,b.alpha)*(hot?1.8:1));
        if (alpha<0.02) continue;
        ctx.save();ctx.globalAlpha=alpha;ctx.strokeStyle=es.color;
        ctx.lineWidth=es.w*(hot?1.7:1);
        if (es.dash.length){ctx.setLineDash(es.dash);ctx.lineDashOffset=-t*20;}
        if (e.type==='semantic'||e.type==='pair') {
            const mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
            const dx=b.x-a.x,dy=b.y-a.y;
            const bx=mx-dy*0.2,by=my+dx*0.2;
            ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.quadraticCurveTo(bx,by,b.x,b.y);ctx.stroke();
        } else {
            ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
            if (e.type==='follows') {
                ctx.setLineDash([]);
                const dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1;
                const tx=b.x-(dx/d)*(b.r+3),ty=b.y-(dy/d)*(b.r+3);
                const ang=Math.atan2(dy,dx);
                ctx.beginPath();ctx.moveTo(tx,ty);
                ctx.lineTo(tx-9*Math.cos(ang-.38),ty-9*Math.sin(ang-.38));
                ctx.lineTo(tx-9*Math.cos(ang+.38),ty-9*Math.sin(ang+.38));
                ctx.closePath();ctx.fillStyle=es.color;ctx.fill();
            }
        }
        ctx.restore();
    }
}

function drawNodes(ctx) {
    const t=MG.tick*0.022;
    const diff=MG.diffMode&&MG.activeFrameIdx>0?computeDiff(MG.activeFrameIdx):{added:new Set(),removed:new Set()};
    const sorted=[...MG.nodes.values()].sort((a,b)=>(a.hot?1:0)-(b.hot?1:0));

    for (const n of sorted) {
        if (n.alpha<0.005) continue;
        ctx.save();ctx.globalAlpha=n.alpha;
        const r=n.r*(1+Math.sin(t+n.pulse)*0.05);
        const injected=MG.injectedContext.has(n.id);
        const graphSub=n.graphSub;
        const isAdded=diff.added.has(n.id);
        const isRemoved=diff.removed.has(n.id);

        // Session view: use frame colour if multi-frame
        const nodeColor=MG.sessionView&&n.frameSet.size>0?n.sessionColor:n.ns.color;

        if (n.ghost||n.hidden) {
            const outOfCtx = !n.inContext && MG.inContextIds.size>0;
            ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);
            ctx.strokeStyle=nodeColor;ctx.lineWidth=0.5;
            // Out-of-context nodes render slightly brighter than pure ghosts
            ctx.globalAlpha=n.alpha*(outOfCtx?0.28:0.18);ctx.stroke();
        } else {
            // Glow
            const g=ctx.createRadialGradient(n.x,n.y,r*.15,n.x,n.y,r*3);
            g.addColorStop(0,nodeColor+'28');g.addColorStop(1,'transparent');
            ctx.beginPath();ctx.arc(n.x,n.y,r*3,0,Math.PI*2);ctx.fillStyle=g;ctx.fill();

            // Fill
            const g2=ctx.createRadialGradient(n.x-r*.3,n.y-r*.3,r*.05,n.x,n.y,r);
            g2.addColorStop(0,lighten(nodeColor,40));g2.addColorStop(1,nodeColor);
            ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);ctx.fillStyle=g2;ctx.globalAlpha=n.alpha;ctx.fill();

            // Border
            ctx.beginPath();ctx.arc(n.x,n.y,r+1,0,Math.PI*2);
            ctx.strokeStyle=nodeColor;ctx.lineWidth=n.hot?2.5:.8;
            ctx.globalAlpha=n.hot?1:.7;ctx.stroke();

            // Relevance arc
            if (n.score>0.05) {
                ctx.beginPath();ctx.arc(n.x,n.y,r+4,-Math.PI/2,-Math.PI/2+Math.PI*2*Math.min(1,n.rel));
                ctx.strokeStyle=nodeColor;ctx.lineWidth=1.5;ctx.globalAlpha=.4;ctx.stroke();
            }

            // Session view: frame membership indicator dots
            if (MG.sessionView&&n.frameSet.size>1) {
                const idxs=[...n.frameSet].slice(0,5);
                idxs.forEach((fi,i)=>{
                    const ang=-Math.PI/2+(i/idxs.length)*Math.PI*2;
                    const dx=Math.cos(ang)*(r+9),dy=Math.sin(ang)*(r+9);
                    ctx.beginPath();ctx.arc(n.x+dx,n.y+dy,2.2,0,Math.PI*2);
                    ctx.fillStyle=frameColor(fi);ctx.globalAlpha=0.9;ctx.fill();
                });
            }

            // Diff indicators
            if (isAdded) {
                ctx.beginPath();ctx.arc(n.x,n.y,r+7,0,Math.PI*2);
                ctx.strokeStyle='#10b981';ctx.lineWidth=2;ctx.globalAlpha=0.8;ctx.stroke();
            }
            if (isRemoved) {
                ctx.beginPath();ctx.arc(n.x,n.y,r+7,0,Math.PI*2);
                ctx.strokeStyle='#ef4444';ctx.lineWidth=2;ctx.globalAlpha=0.5;ctx.setLineDash([3,3]);ctx.stroke();ctx.setLineDash([]);
            }

            // In-context solid cyan ring
            if (n.inContext && MG.inContextIds.size>0) {
                ctx.beginPath();ctx.arc(n.x,n.y,r+9,0,Math.PI*2);
                ctx.strokeStyle='#22d3ee';ctx.lineWidth=2;ctx.globalAlpha=0.75;
                ctx.shadowColor='#22d3ee';ctx.shadowBlur=8;
                ctx.stroke();ctx.shadowBlur=0;
            }
            // Out-of-context dim dashed ring (retrieved but not sent to LLM)
            else if (!n.inContext && MG.inContextIds.size>0) {
                ctx.beginPath();ctx.arc(n.x,n.y,r+6,0,Math.PI*2);
                ctx.strokeStyle='rgba(255,255,255,0.12)';ctx.lineWidth=1;ctx.globalAlpha=0.6;
                ctx.setLineDash([2,5]);ctx.stroke();ctx.setLineDash([]);
            }

            // Graph-sub ring
            if (graphSub) {
                const gsCol=(MG.theme?.accentTool)||'#06b6d4';
                ctx.beginPath();ctx.arc(n.x,n.y,r+6,0,Math.PI*2);
                ctx.strokeStyle=gsCol;ctx.lineWidth=1.2;ctx.globalAlpha=0.55;
                ctx.setLineDash([3,2]);ctx.stroke();ctx.setLineDash([]);
            }

            // Injected ring
            if (injected) {
                const iCol=(MG.theme?.accentSuccess)||'#10b981';
                ctx.beginPath();ctx.arc(n.x,n.y,r+(graphSub?12:8),0,Math.PI*2);
                ctx.strokeStyle=iCol;ctx.lineWidth=2;ctx.globalAlpha=0.7;
                ctx.setLineDash([4,3]);ctx.stroke();ctx.setLineDash([]);
            }
        }

        // Glyph
        ctx.globalAlpha=n.alpha*(n.ghost||n.hidden?.15:.9);
        ctx.font=`bold ${Math.max(7,r*.85)}px monospace`;
        ctx.textAlign='center';ctx.textBaseline='middle';
        ctx.fillStyle=(n.ghost||n.hidden)?nodeColor:'#fff';
        ctx.fillText(n.ns.g,n.x,n.y);

        // Label
        if (n.hot||(!n.ghost&&!n.hidden&&n.score>.6&&MG.zoom>.55)) {
            const lbl=n.text.length>30?n.text.slice(0,30)+'…':n.text;
            ctx.font='10px monospace';ctx.textAlign='center';ctx.textBaseline='top';
            const tw=ctx.measureText(lbl).width;
            const labelOffY=r+(injected?14:graphSub?10:7);
            const lx=n.x-tw/2-5,ly=n.y+labelOffY;
            ctx.globalAlpha=n.alpha*.88;ctx.fillStyle=COLORS.labelBg;
            rrect(ctx,lx,ly,tw+10,15,4);ctx.fill();
            ctx.fillStyle=n.hot?'#fff':nodeColor;ctx.fillText(lbl,n.x,ly+2);
        }

        // Session view: frame count badge
        if (MG.sessionView&&n.frameSet.size>1&&!n.ghost&&!n.hidden) {
            ctx.font='bold 8px monospace';ctx.textAlign='center';ctx.textBaseline='middle';
            ctx.fillStyle='#fff';ctx.globalAlpha=0.9;
            ctx.fillText(`×${n.frameSet.size}`,n.x+r*.6,n.y-r*.6);
        }

        ctx.restore();
    }
}

function drawHUD(ctx,W,H) {
    const visCount=[...MG.nodes.values()].filter(n=>!n.hidden).length;
    const graphSubCount=[...MG.nodes.values()].filter(n=>n.graphSub).length;
    ctx.save();
    ctx.font='10px monospace';ctx.textAlign='left';ctx.fillStyle=COLORS.hudText;

    // Frame indicator in HUD
    if (MG.sessionView) {
        ctx.fillStyle='#f59e0b';
        ctx.fillText(`⊙ Session view — ${MG.frames.length} frames · ${visCount} unique nodes`,14,H-12);
    } else if (MG.activeFrameIdx>=0) {
        ctx.fillStyle=frameColor(MG.activeFrameIdx);
        ctx.fillText(`⬡ Frame ${MG.activeFrameIdx+1}/${MG.frames.length} · ${visCount}/${MG.nodes.size} nodes`,14,H-12);
        if (MG.diffMode&&MG.activeFrameIdx>0) {
            const {added,removed}=computeDiff(MG.activeFrameIdx);
            ctx.fillStyle='#10b981';ctx.fillText(`+${added.size}`,14,H-26);
            ctx.fillStyle='#ef4444';ctx.fillText(`−${removed.size}`,40,H-26);
        }
    } else {
        ctx.fillStyle = MG.livePreview ? '#f59e0b' : COLORS.hudText;
        const liveTag = MG.livePreview ? '⟳ PREVIEW  ' : '';
        const ctxTag  = MG.inContextIds.size>0 ? `  [${MG.inContextIds.size} in-ctx]` : '';
        ctx.fillText(`${liveTag}${visCount}/${MG.nodes.size} nodes · ${MG.edges.length} edges · ×${MG.zoom.toFixed(2)}${ctxTag}`,14,H-12);
    }

    if (graphSubCount>0) {
        const gsCol=(MG.theme?.accentTool)||'#06b6d4';
        ctx.fillStyle=gsCol;ctx.textAlign='left';
        ctx.fillText(`⇄ ${graphSubCount} graph sub`,14,H-26);
    }
    if (MG.injectedContext.size>0) {
        const col=(MG.theme?.accentSuccess)||'#10b981';
        ctx.fillStyle=col;ctx.textAlign='right';
        ctx.fillText(`${MG.injectedContext.size} ctx node${MG.injectedContext.size>1?'s':''}`,W-14,H-12);
    }
    if (MG.loading) {
        ctx.fillStyle=COLORS.hudLoading;ctx.textAlign='center';
        ctx.fillText('loading'+'·'.repeat((Date.now()/350|0)%4),W/2,22);
    }
    if (MG.nodes.size===0&&!MG.loading) {
        ctx.fillStyle=COLORS.emptyText;ctx.textAlign='center';ctx.font='12px monospace';
        ctx.fillText('Fetch context in Context Inspector, or send a message',W/2,H/2-10);
        ctx.font='10px monospace';
        ctx.fillText('_MG.debugIngest(data)  to test with custom data',W/2,H/2+14);
    }
    ctx.restore();
}

// ─── Hit test ─────────────────────────────────────────────────────────
function worldXY(sx,sy) { return{x:(sx-MG.W/2-MG.pan.x)/MG.zoom,y:(sy-MG.H/2-MG.pan.y)/MG.zoom}; }
function nodeAt(sx,sy) {
    const{x,y}=worldXY(sx,sy);
    let best=null,bd=Infinity;
    for(const n of MG.nodes.values()){
        if(n.hidden&&!n.hot) continue;
        const d=Math.hypot(n.x-x,n.y-y);
        if(d<n.r+12&&d<bd){best=n;bd=d;}
    }
    return best;
}

// ─── Events ───────────────────────────────────────────────────────────
function initEvents(canvas) {
    let panSX=0,panSY=0,panOX=0,panOY=0;
    canvas.addEventListener('mousemove',e=>{
        const r=canvas.getBoundingClientRect(),sx=e.clientX-r.left,sy=e.clientY-r.top;
        if(MG.dragging){const w=worldXY(sx,sy);MG.dragging.fx=w.x;MG.dragging.fy=w.y;return;}
        if(MG.isPanning){MG.pan.x=panOX+(sx-panSX);MG.pan.y=panOY+(sy-panSY);return;}
        const hit=nodeAt(sx,sy);
        if(hit!==MG.hovered){
            MG.hovered=hit;canvas.style.cursor=hit?'pointer':'grab';
            if(hit) showDetail(hit); else if(!MG.selected) hideDetail();
            updateAlpha();
        }
    });
    canvas.addEventListener('mousedown',e=>{
        const r=canvas.getBoundingClientRect(),sx=e.clientX-r.left,sy=e.clientY-r.top;
        const hit=nodeAt(sx,sy);
        if(hit){MG.dragging=hit;}
        else{MG.isPanning=true;panSX=sx;panSY=sy;panOX=MG.pan.x;panOY=MG.pan.y;canvas.style.cursor='grabbing';}
    });
    canvas.addEventListener('mouseup',()=>{
        if(MG.dragging){MG.dragging.fx=MG.dragging.fy=null;}
        MG.dragging=null;MG.isPanning=false;canvas.style.cursor=MG.hovered?'pointer':'grab';
    });
    canvas.addEventListener('click',e=>{
        const r=canvas.getBoundingClientRect();
        const hit=nodeAt(e.clientX-r.left,e.clientY-r.top);
        if(hit){MG.selected=MG.selected?.id===hit.id?null:hit;MG.selected?showDetail(MG.selected):hideDetail();updateAlpha();}
        else{MG.selected=null;hideDetail();updateAlpha();}
    });
    canvas.addEventListener('dblclick',e=>{
        const r=canvas.getBoundingClientRect();
        const hit=nodeAt(e.clientX-r.left,e.clientY-r.top);
        if(hit) showExpandPanel(hit);
    });
    canvas.addEventListener('wheel',e=>{
        e.preventDefault();
        const r=canvas.getBoundingClientRect(),sx=e.clientX-r.left,sy=e.clientY-r.top;
        const f=e.deltaY>0?.88:1.14;
        const nz=Math.max(.15,Math.min(4,MG.zoom*f));
        MG.pan.x=sx-MG.W/2-(sx-MG.W/2-MG.pan.x)*(nz/MG.zoom);
        MG.pan.y=sy-MG.H/2-(sy-MG.H/2-MG.pan.y)*(nz/MG.zoom);
        MG.zoom=nz;
    },{passive:false});
}

// ─── Frame Bar ────────────────────────────────────────────────────────
function renderFrameBar() {
    const bar=document.getElementById('mg-frame-bar');
    if(!bar) return;
    const pf=MG.theme||{};
    const accent=pf.accentStage||'#3b82f6';

    if(!MG.frameBarOpen||!MG.frames.length) {
        bar.innerHTML=`
          <div style="display:flex;align-items:center;gap:8px;padding:5px 12px">
            <span style="font-size:9px;color:${pf.text||'#334155'};opacity:.6">
              ${MG.frames.length} frame${MG.frames.length!==1?'s':''} captured
            </span>
            <button class="mg-fbar-btn" onclick="MG_captureNow()" title="Capture current graph state as a frame" style="font-size:9px">⊕ Capture now</button>
            ${MG.frames.length?`<button class="mg-fbar-btn" onclick="MG_frameBarToggle()" style="margin-left:auto">▲ Show frames</button>`:''}
          </div>`;
        requestAnimationFrame(resize); // canvas rect shifts when bar changes height
        return;
    }

    // Build thumb row
    const thumbs=MG.frames.map((f,i)=>{
        const col=frameColor(i);
        const isActive=MG.activeFrameIdx===i&&!MG.sessionView;
        const ts=new Date(f.ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
        const truncQ=f.label.length>22?f.label.slice(0,22)+'…':f.label;
        const histNote=f.historyCount>0?` +${f.historyCount}h`:'';
        // Similarity badge vs previous frame
        let simBadge='';
        if (i>0&&MG.frames[i-1]._fp&&f._fp) {
            const sim=_fpSimilarity(MG.frames[i-1]._fp,f._fp);
            const pct=Math.round(sim*100);
            const simCol=pct>60?'#ef4444':pct>30?'#f59e0b':'#10b981';
            simBadge=`<div style="font-size:7px;color:${simCol};text-align:right">${pct}% same</div>`;
        }
        return `
          <div class="mg-frame-thumb${isActive?' active':''}"
               onclick="MG_activateFrame(${i})"
               title="${escH(f.label)}\n${ts} · ${f.nodeCount} retrieved${f.historyCount?` · ${f.historyCount} history`:''}"
               style="border-color:${isActive?col:''}">
            <div class="mg-ft-num" style="color:${col}">F${i+1}</div>
            <div class="mg-ft-bar" style="background:${col}22">
              <div style="height:100%;width:${Math.min(100,(f.nodeCount/50)*100)}%;background:${col};border-radius:1px"></div>
            </div>
            <div class="mg-ft-q" title="${escH(f.label)}">${escH(truncQ)}</div>
            <div class="mg-ft-ts">${ts} · <span style="color:${col}">${f.nodeCount}n${histNote}</span></div>
            ${simBadge}
          </div>`;
    }).join('');

    const scrubVal=MG.activeFrameIdx>=0?MG.activeFrameIdx:MG.frames.length-1;

    bar.innerHTML=`
      <div style="display:flex;align-items:center;gap:6px;padding:5px 10px 3px">
        <span style="font-size:9px;color:${pf.text||'#334155'};white-space:nowrap;flex-shrink:0">FRAMES</span>
        <div id="mg-ft-scroll" style="display:flex;gap:5px;overflow-x:auto;flex:1;padding:2px 0;scrollbar-width:thin;">
          ${thumbs}
        </div>
        <div style="display:flex;gap:4px;flex-shrink:0">
          <button class="mg-fbar-btn${MG.sessionView?' mg-on':''}" onclick="MG_sessionView()" title="Show all frames composited">⊙ Session</button>
          <button class="mg-fbar-btn${MG.diffMode?' mg-on':''}" onclick="MG_toggleDiff()" title="Diff vs previous frame">Δ Diff</button>
          <button class="mg-fbar-btn" onclick="MG_captureNow()" title="Capture current state">⊕ Cap</button>
          <button class="mg-fbar-btn" onclick="MG_frameBarToggle()">▼</button>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;padding:0 10px 4px">
        <span style="font-size:9px;color:${pf.text||'#334155'};opacity:.5;white-space:nowrap">
          ${MG.sessionView?'Session view':MG.activeFrameIdx>=0?`Frame ${MG.activeFrameIdx+1}/${MG.frames.length}`:'Live'}
        </span>
        <input type="range" id="mg-frame-scrubber" min="0" max="${Math.max(0,MG.frames.length-1)}"
               value="${scrubVal}" oninput="MG_scrub(+this.value)"
               style="flex:1;height:3px;cursor:pointer">
        <span style="font-size:9px;color:${accent};white-space:nowrap" id="mg-scrub-label">
          ${MG.frames.length?`${scrubVal+1}/${MG.frames.length}`:''}
        </span>
        <button class="mg-fbar-btn" onclick="MG_liveView()" title="Return to live view" style="font-size:9px">↺ Live</button>
      </div>`;

    // Scroll to active thumb + sync canvas size
    requestAnimationFrame(()=>{
        resize(); // canvas rect shifts when bar opens/changes
        const scroll=document.getElementById('mg-ft-scroll');
        if(scroll&&MG.activeFrameIdx>=0){
            const thumbEl=scroll.children[MG.activeFrameIdx];
            if(thumbEl) thumbEl.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
        }
    });
}

function _updateScrubber() {
    const el=document.getElementById('mg-frame-scrubber');
    if(el) {
        el.max=Math.max(0,MG.frames.length-1);
        el.value=MG.activeFrameIdx>=0?MG.activeFrameIdx:MG.frames.length-1;
    }
    const lbl=document.getElementById('mg-scrub-label');
    if(lbl) {
        const v=MG.activeFrameIdx>=0?MG.activeFrameIdx:MG.frames.length-1;
        lbl.textContent=MG.frames.length?`${v+1}/${MG.frames.length}`:'';
    }
}

// Global frame controls
window.MG_activateFrame = idx => activateFrame(idx);
window.MG_sessionView   = () => activateSessionView();
window.MG_liveView      = () => activateLiveView();
window.MG_scrub         = idx => activateFrame(idx);
window.MG_captureNow    = () => { captureFrame(MG._pendingRawData||{_query:'manual capture'}); };
window.MG_toggleDiff    = () => { MG.diffMode=!MG.diffMode; renderFrameBar(); };
window.MG_frameBarToggle= () => { MG.frameBarOpen=!MG.frameBarOpen; renderFrameBar(); };

// ─── Detail panel ─────────────────────────────────────────────────────
function showDetail(node) {
    let el=document.getElementById('mg-detail');
    if(!el){el=document.createElement('div');el.id='mg-detail';document.body.appendChild(el);}
    const pf=MG.theme||{};
    const sc={
        vector_session:'#3b82f6',vector_xsession:'#60a5fa',graph_rerank:'#8b5cf6',
        vector_longterm:'#0ea5e9',chunk_reassembled:'#f59e0b',graph_traverse:'#10b981',
        keyword_neo4j:'#06b6d4',entity_recall:'#34d399',neighbour_swap:'#a78bfa',
        recalled_exchange:'#818cf8',focus:'#fbbf24',graph:'#10b981',history:'#64748b',
    };
    const c=sc[node.source]||pf.text||'#475569';
    const injected=MG.injectedContext.has(node.id);
    const layer=nodeLayer(node);
    const layerColor=layer==='vector'?'#3b82f6':layer==='graph'?'#10b981':'#f59e0b';
    const graphSubColor='#06b6d4';

    // In session view: show which frames this node appeared in
    const frameBadges=MG.sessionView&&node.frameSet.size>0
        ?[...node.frameSet].map(fi=>`<span style="background:${frameColor(fi)}22;color:${frameColor(fi)};font-size:8px;padding:1px 4px;border-radius:2px">F${fi+1}</span>`).join('')
        :'';

    el.className='mg-detail';
    el.innerHTML=`
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap">
        <span style="color:${node.ns.color};font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">${node.type.replace(/_/g,' ')}</span>
        <span style="background:${c}22;color:${c};font-size:9px;padding:1px 5px;border-radius:3px">${node.source||'—'}</span>
        <span style="background:${layerColor}22;color:${layerColor};font-size:9px;padding:1px 5px;border-radius:3px;margin-left:auto">${layer}</span>
        ${node.graphSub?`<span style="background:${graphSubColor}22;color:${graphSubColor};font-size:9px;padding:1px 5px;border-radius:3px">⇄ graph sub</span>`:''}
      </div>
      ${frameBadges?`<div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:6px">${frameBadges}</div>`:''}
      <div style="font-size:11px;color:${pf.text||'#64748b'};line-height:1.5;margin-bottom:10px;max-height:80px;overflow-y:auto;word-break:break-word">${escH(node.text)}</div>
      <div style="display:flex;flex-direction:column;gap:5px;margin-bottom:8px">
        ${sbar('relevance',node.score,node.ns.color)}
        ${node.vector_score>0?sbar('vector',node.vector_score,'#3b82f6'):''}
        ${node.graph_score>0?sbar('graph',node.graph_score,'#10b981'):''}
        ${node.keyword_score>0?sbar('keyword',node.keyword_score,'#06b6d4'):''}
      </div>
      <div style="display:flex;gap:5px;flex-wrap:wrap">
        <button onclick="MG_showExpand('${node.id}')" class="mg-da-btn">⊕ Expand</button>
        <button onclick="MG_toggleInject('${node.id}')" class="mg-da-btn" style="${injected?`background:#10b98122;border-color:#10b981;color:#10b981`:''}">${injected?'✓ In context':'+ Context'}</button>
        <button onclick="MG_pin('${node.id}')"  class="mg-da-btn">📌 Pin</button>
        <button onclick="MG_hide('${node.id}')" class="mg-da-btn">✕</button>
      </div>`;
    const cr=MG.canvas.getBoundingClientRect();
    const sx=(node.x*MG.zoom+MG.W/2+MG.pan.x)+cr.left;
    const sy=(node.y*MG.zoom+MG.H/2+MG.pan.y)+cr.top;
    el.style.left=Math.min(sx+18,window.innerWidth-285)+'px';
    el.style.top=Math.max(10,Math.min(sy-40,window.innerHeight-280))+'px';
    el.style.display='block';
}
function hideDetail(){const e=document.getElementById('mg-detail');if(e)e.style.display='none';}

function sbar(l,v,c){
    const pf=MG.theme||{};
    return`<div style="display:flex;align-items:center;gap:5px;font-size:9px;color:${pf.text||'#334155'}">
  <span style="width:46px">${l}</span>
  <div style="flex:1;height:3px;background:${pf.bg||'#0e1e33'};border-radius:2px;overflow:hidden">
    <div style="width:${((+v||0)*100).toFixed(0)}%;height:100%;background:${c};border-radius:2px"></div>
  </div>
  <span style="width:30px;text-align:right">${((+v||0)*100).toFixed(0)}%</span>
</div>`;
}

// ─── Expand panel (unchanged from v5.1) ────────────────────────────────
async function showExpandPanel(node) {
    if(!node) return;
    closeExpandPanel();
    MG.loading=true;
    let candidates=[];
    try {
        const res=await fetch(`${API_BASE}/api/context/node_neighbours`,{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({node_id:node.id,query:MG.currentQuery,session_id:MG.sessionId,n_hops:2,k_per_hop:8}),
        });
        if(!res.ok) throw new Error(res.statusText);
        const data=await res.json();
        candidates=(data.nodes||[]).map(n=>({
            id:n.id||`exp_${hash(n.text||node.id)}`,text:n.text||n.properties?.text||n.id,
            type:n.type||'entity',score:n.score||0.35,vector_score:0,graph_score:n.score||0.35,
            keyword_score:0,source:'expanded',metadata:n.properties||{},rel:n.rel||'',
            alreadyLoaded:MG.nodes.has(n.id||`exp_${hash(n.text||node.id)}`),checked:false,
        }));
    } catch(err) {
        const sentences=node.text.match(/[^.!?]+[.!?]+/g)||[node.text];
        candidates=sentences.slice(0,6).filter(s=>s.trim().length>15).map((s,i)=>({
            id:`frag_${hash(s)}`,text:s.trim(),type:node.type==='query'?'response':'entity',
            score:0.35+(0.1*(5-i)/5),vector_score:0.3,graph_score:0.2,keyword_score:0,
            source:'expanded_local',metadata:{},rel:'fragment',
            alreadyLoaded:MG.nodes.has(`frag_${hash(s)}`),checked:false,
        }));
    }
    MG.loading=false;
    MG.expandPanel={sourceId:node.id,candidates};
    renderExpandPanel(node);
}

function renderExpandPanel(sourceNode) {
    let el=document.getElementById('mg-expand');
    if(!el){el=document.createElement('div');el.id='mg-expand';document.body.appendChild(el);}
    const ep=MG.expandPanel;
    const accent=(MG.theme?.accentStage)||'#3b82f6';
    const success=(MG.theme?.accentSuccess)||'#10b981';
    const rows=ep.candidates.map((c,i)=>{
        const ns=NS[c.type]||NS.default;
        return`<div class="mg-ep-item${c.checked?' checked':''}" data-idx="${i}">
            <label style="display:flex;align-items:flex-start;gap:8px;cursor:pointer;width:100%">
                <input type="checkbox" class="mg-ep-cb" data-idx="${i}" ${c.checked?'checked':''} style="margin-top:2px;accent-color:${accent};flex-shrink:0">
                <div style="flex:1;min-width:0">
                    <div style="display:flex;align-items:center;gap:5px;margin-bottom:2px;flex-wrap:wrap">
                        <span style="color:${ns.color};font-size:9px;font-weight:700;text-transform:uppercase">${c.type.replace(/_/g,' ')}</span>
                        ${c.rel?`<span class="mg-ep-type">${escH(c.rel)}</span>`:''}
                        <span class="mg-ep-score" style="margin-left:auto">${(c.score*100).toFixed(0)}%</span>
                        ${c.alreadyLoaded?`<span style="color:${success};font-size:8px">✓ loaded</span>`:''}
                    </div>
                    <div class="mg-ep-text">${escH(c.text.slice(0,120))}${c.text.length>120?'…':''}</div>
                </div>
            </label>
        </div>`;
    }).join('');
    el.innerHTML=`
        <div class="mg-ep-hdr">
            <span>⊕ Expand: <em style="font-style:normal;opacity:.7">${escH(sourceNode.text.slice(0,40))}${sourceNode.text.length>40?'…':''}</em></span>
            <button onclick="closeExpandPanel()" style="background:none;border:none;cursor:pointer;color:inherit;font-size:14px;padding:0 4px">✕</button>
        </div>
        <div class="mg-ep-body"><div style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:9px;color:${(MG.theme?.textSecondary)||'#64748b'}">
            <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                <input type="checkbox" id="mg-ep-selall" style="accent-color:${accent}"> select all
            </label>
            <span style="margin-left:auto"><span id="mg-ep-count">0</span> selected</span>
        </div>
        <div class="mg-ep-list">${rows}</div></div>
        <div class="mg-ep-footer">
            <button class="mg-ep-add-btn" onclick="MG_expandCommit()">+ Add to graph</button>
            <button class="mg-ep-inject-btn" onclick="MG_expandInject()">⚡ Add to context</button>
            <button class="mg-ep-cancel" onclick="closeExpandPanel()">Cancel</button>
        </div>`;
    if(MG.canvas){
        const cr=MG.canvas.getBoundingClientRect();
        const sx=(sourceNode.x*MG.zoom+MG.W/2+MG.pan.x)+cr.left;
        const sy=(sourceNode.y*MG.zoom+MG.H/2+MG.pan.y)+cr.top;
        el.style.left=Math.min(sx+20,window.innerWidth-340)+'px';
        el.style.top=Math.max(10,Math.min(sy-60,window.innerHeight-480))+'px';
    }
    el.style.display='block';
    el.querySelectorAll('.mg-ep-cb').forEach(cb=>{
        cb.addEventListener('change',e=>{
            const idx=+e.target.dataset.idx;
            ep.candidates[idx].checked=e.target.checked;
            e.target.closest('.mg-ep-item').classList.toggle('checked',e.target.checked);
            updateEpCount();
        });
    });
    const selAll=el.querySelector('#mg-ep-selall');
    selAll.addEventListener('change',e=>{
        ep.candidates.forEach(c=>c.checked=e.target.checked);
        el.querySelectorAll('.mg-ep-cb').forEach(cb=>{cb.checked=e.target.checked;cb.closest('.mg-ep-item').classList.toggle('checked',e.target.checked);});
        updateEpCount();
    });
    updateEpCount();
    function updateEpCount(){const n=ep.candidates.filter(c=>c.checked).length;const el2=el.querySelector('#mg-ep-count');if(el2)el2.textContent=n;}
}

function closeExpandPanel(){const el=document.getElementById('mg-expand');if(el)el.style.display='none';MG.expandPanel=null;}

window.MG_expandCommit=function(){
    const ep=MG.expandPanel;if(!ep)return;
    const sel=ep.candidates.filter(c=>c.checked);if(!sel.length)return;
    let added=0;
    for(const c of sel){
        if(MG.nodes.size>=MG.nodeLimit)break;
        if(!MG.nodes.has(c.id)){MG.nodes.set(c.id,new GNode(c.id,c));added++;}
        addEdge(ep.sourceId,c.id,isGraphSubSource(c.source)?'graph':'semantic',c.score,c.rel||'');
    }
    buildSemanticEdges();updateAlpha();simReheat();
    closeExpandPanel();
};
window.MG_expandInject=function(){
    const ep=MG.expandPanel;if(!ep)return;
    const sel=ep.candidates.filter(c=>c.checked);if(!sel.length)return;
    for(const c of sel){
        if(MG.nodes.size<MG.nodeLimit&&!MG.nodes.has(c.id))MG.nodes.set(c.id,new GNode(c.id,c));
        addEdge(ep.sourceId,c.id,isGraphSubSource(c.source)?'graph':'semantic',c.score,c.rel||'');
        MG.injectedContext.set(c.id,{id:c.id,text:c.text,type:c.type,score:c.score});
    }
    buildSemanticEdges();updateAlpha();simReheat();
    closeExpandPanel();renderCtxTray();
};

// ─── Context injection tray (unchanged) ───────────────────────────────
function renderCtxTray() {
    let el=document.getElementById('mg-ctx-tray');
    if(!el){el=document.createElement('div');el.id='mg-ctx-tray';document.body.appendChild(el);}
    if(MG.injectedContext.size===0){el.style.display='none';return;}
    const success=(MG.theme?.accentSuccess)||'#10b981';
    const chips=[...MG.injectedContext.values()].map(n=>`
        <span class="mg-ct-chip" title="${escH(n.text)}">
            ${escH(n.text.slice(0,30))}${n.text.length>30?'…':''}
            <button class="mg-ct-chip-x" onclick="MG_removeInject('${n.id}')">×</button>
        </span>`).join('');
    el.innerHTML=`
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span class="mg-ct-label">⚡ Query context (${MG.injectedContext.size})</span>
            <div style="display:flex;flex-wrap:wrap;gap:4px;flex:1">${chips}</div>
            <button class="mg-ct-send-btn" onclick="MG_sendWithContext()">Send with context</button>
            <button class="mg-ct-clear" onclick="MG_clearInject()">clear</button>
        </div>`;
    el.style.display='block';
}

window.MG_toggleInject=function(id){
    const n=MG.nodes.get(id);if(!n)return;
    if(MG.injectedContext.has(id))MG.injectedContext.delete(id);
    else MG.injectedContext.set(id,{id,text:n.text,type:n.type,score:n.score});
    renderCtxTray();if(MG.selected?.id===id)showDetail(MG.selected);
};
window.MG_removeInject=function(id){MG.injectedContext.delete(id);renderCtxTray();if(MG.selected?.id===id)showDetail(MG.selected);};
window.MG_clearInject=function(){MG.injectedContext.clear();renderCtxTray();};
window.MG_sendWithContext=function(){
    const ctx=[...MG.injectedContext.values()];if(!ctx.length)return;
    if(typeof window.MG_onSendWithContext==='function'){window.MG_onSendWithContext(ctx);return;}
    const input=document.getElementById('messageInput');
    if(input){
        const existing=input.value.trim();
        const prefix=ctx.map(n=>`[CTX:${n.type}] ${n.text}`).join('\n');
        input.value=prefix+(existing?'\n\n'+existing:'');
        input.dispatchEvent(new Event('input',{bubbles:true}));
        input.focus();input.selectionStart=input.selectionEnd=input.value.length;
    }
};

// ─── Legend ────────────────────────────────────────────────────────────
function rebuildLegend() {
    const leg=document.getElementById('mg-leg');if(!leg) return;
    leg.innerHTML=`
        <span class="mg-li"><i style="background:${NS.query.color}"></i>Query</span>
        <span class="mg-li"><i style="background:${NS.response.color}"></i>Response</span>
        <span class="mg-li"><i style="background:${NS.entity.color}"></i>Entity</span>
        <span class="mg-li"><i style="background:${NS.document.color}"></i>Document</span>
        <span class="mg-li"><i style="background:${NS.focus.color}"></i>Focus</span>
        <span class="mg-sep"></span>
        <span class="mg-li"><i style="background:${NS.keyword_neo4j.color}"></i>Keyword</span>
        <span class="mg-li"><i style="background:${NS.entity_recall.color}"></i>Entity↳</span>
        <span class="mg-sep"></span>
        <span class="mg-li"><em class="mg-el" style="border-color:${ES.semantic.color};border-style:dashed"></em>semantic</span>
        <span class="mg-li"><em class="mg-el" style="border-color:${ES.graph.color}"></em>graph</span>
        <span class="mg-li"><em class="mg-el" style="border-color:${ES.follows.color}"></em>follows</span>
        <span class="mg-sep"></span>
        <span class="mg-li" style="color:#10b981">● added</span>
        <span class="mg-li" style="color:#ef4444">○ removed</span>
        <span class="mg-li" style="color:#f59e0b">⊙ session</span>
        <span class="mg-sep"></span>
        <span class="mg-li" style="color:#22d3ee">◎ in-context</span>
        <span class="mg-li" style="color:rgba(255,255,255,0.25)">◌ out-of-ctx</span>`;
}

// ─── Window ────────────────────────────────────────────────────────────
function createWin() {
    if(document.getElementById('mg-win')) return;
    const win=document.createElement('div');win.id='mg-win';
    win.innerHTML=`
      <div id="mg-bar">
        <span class="mg-logo">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="5" r="2.2"/><circle cx="4" cy="19" r="2.2"/><circle cx="20" cy="19" r="2.2"/>
            <line x1="12" y1="7.2" x2="4.8" y2="17"/><line x1="12" y1="7.2" x2="19.2" y2="17"/>
            <line x1="6.2" y1="19" x2="17.8" y2="19"/>
          </svg>MEMORY GRAPH
        </span>
        <div id="mg-modes">
          <button class="mg-mb ${MG.mode==='semantic'?'mg-on':''}" onclick="MG_mode('semantic')">◌ Semantic</button>
          <button class="mg-mb ${MG.mode==='blend'   ?'mg-on':''}" onclick="MG_mode('blend')"   >⊛ Blend</button>
          <button class="mg-mb ${MG.mode==='graph'   ?'mg-on':''}" onclick="MG_mode('graph')"   >— Graph</button>
        </div>
        <div id="mg-ctrls">
          <label class="mg-lbl" title="Max nodes">
            n<input type="range" min="8" max="80" value="${MG.nodeLimit}" oninput="MG_limit(+this.value)" class="mg-sl">
            <span id="mg-nv">${MG.nodeLimit}</span>
          </label>
          <label class="mg-lbl" title="Ghost threshold">
            👁<input type="range" min="0" max="70" value="${MG.focusThreshold*100|0}" oninput="MG_thresh(+this.value/100)" class="mg-sl">
            <span id="mg-tv">${MG.focusThreshold*100|0}%</span>
          </label>
          <button class="mg-btn" onclick="MG_reset()">⊙</button>
          <button class="mg-btn" onclick="MG_clear()">✕ clear</button>
          <button class="mg-btn mg-bx" onclick="MG_close()">✕</button>
        </div>
      </div>
      <div id="mg-wrap"><canvas id="mg-cv"></canvas></div>
      <div id="mg-leg"></div>
      <div id="mg-frame-bar"></div>
      <div id="mg-hint">drag·scroll zoom·dbl-click expand·+ context·drag bg pan · frames: scrub or click thumbs</div>`;
    document.body.appendChild(win);
    makeDrag(win,document.getElementById('mg-bar'));
    const cv=document.getElementById('mg-cv');
    MG.canvas=cv;MG.ctx=cv.getContext('2d');
    resize();
    if (window.ResizeObserver) {
        MG._ro = new ResizeObserver(function(){ resize(); });
        MG._ro.observe(document.getElementById('mg-wrap'));
    } else {
        window.addEventListener('resize', resize);
    }
    initEvents(cv);
    applyTheme();
    rebuildLegend();
    // Seed session ID from the host app before attempting to load persisted frames.
    // MG.sessionId is normally set on first ingest, but on reopen we need it sooner.
    if (!MG.sessionId) MG.sessionId = window.app?.sessionId || '';
    // Always attempt to load frames — MG.frames may exist in memory from a previous
    // open in this page session, but on a fresh page load they'll be empty.
    // loadFrames merges/replaces from localStorage so calling it is always safe.
    var hadFrames = MG.frames.length > 0;
    loadFrames();
    // If we just loaded frames from storage (or already had them), restore the last
    // frame so the graph is populated immediately without requiring "Capture Now".
    if (MG.frames.length > 0 && !hadFrames) {
        // Small defer so canvas dimensions are settled before activateFrame draws
        setTimeout(function() {
            activateFrame(MG.frames.length - 1);
            console.log('[MG] createWin: restored last frame (' + MG.frames.length + ' total)');
        }, 50);
    }
    renderFrameBar();
    loop();
}

function resize(){
    const w=document.getElementById('mg-wrap');if(!w||!MG.canvas)return;
    MG.W=MG.canvas.width=w.clientWidth;MG.H=MG.canvas.height=w.clientHeight;
}

// ─── Frame persistence (localStorage) ─────────────────────────────────
// Frames are keyed by session ID. On close/reopen, session ID may not yet be
// set, so we store a pointer (mg_last_session) to the last-used key.
const MG_STORE_VER = 1;
const MG_STORE_MAX = 50;
const MG_PTR_KEY   = 'mg_last_session';

function _frameKey(sid) {
    var id = sid || MG.sessionId || '';
    return id ? ('mg_frames_' + id) : null;
}

function saveFrames() {
    if (!MG.frames.length) return;
    var sid = MG.sessionId || window.app?.sessionId || '';
    var key = _frameKey(sid);
    if (!key) { console.warn('[MG] saveFrames: no session ID, cannot persist'); return; }
    // Persist session pointer so loadFrames can find this key on reopen
    try { localStorage.setItem(MG_PTR_KEY, sid); } catch(_) {}
    function slim(frames) {
        return frames.map(function(f) {
            return {
                id:f.id, idx:f.idx, label:f.label, query:f.query,
                ts:f.ts, nodeCount:f.nodeCount, historyCount:f.historyCount||0,
                sessionId:f.sessionId, _fp:f._fp,
                nodeSnap:f.nodeSnap, edgeSnap:f.edgeSnap,
                _inContextIds:f._inContextIds||[],
            };
        });
    }
    var cuts = [MG_STORE_MAX, 20, 5];
    for (var i=0; i<cuts.length; i++) {
        try {
            var payload = JSON.stringify({v:MG_STORE_VER, frames:slim(MG.frames.slice(-cuts[i]))});
            localStorage.setItem(key, payload);
            // Verify the write actually stuck (quota errors can be silent in some browsers)
            var verify = localStorage.getItem(key);
            if (!verify || verify.length < 10) {
                console.warn('[MG] saveFrames: write verification failed (data not persisted)');
                throw new Error('write-verify-failed');
            }
            console.debug('[MG] saveFrames: '+MG.frames.length+' frames, '+(payload.length/1024).toFixed(1)+'KB -> '+key);
            return;
        } catch(e) {
            console.warn('[MG] saveFrames attempt '+i+' failed:', e.name);
        }
    }
    console.error('[MG] saveFrames: all attempts failed');
}

function loadFrames() {
    // If frames are already in memory (same page session, window just closed & reopened),
    // don't clobber them from storage — they're already the ground truth.
    if (MG.frames.length > 0) {
        console.log('[MG] loadFrames: ' + MG.frames.length + ' frames already in memory, skipping storage load');
        return;
    }
    // Resolve the key: prefer current session ID (or app's), fall back to stored pointer
    var sid = MG.sessionId || window.app?.sessionId || '';
    var key = _frameKey(sid);
    if (!key) {
        try { sid = localStorage.getItem(MG_PTR_KEY)||''; key = _frameKey(sid); } catch(_) {}
    }
    if (!key) { console.log('[MG] loadFrames: no session key available'); return; }
    console.log('[MG] loadFrames: checking', key);
    try {
        var raw = localStorage.getItem(key);
        if (!raw) {
            // Diagnostic: list all mg_ keys so we can spot key mismatches
            var mgKeys = [];
            try { for (var k in localStorage) { if (k.startsWith('mg_')) mgKeys.push(k); } } catch(_) {}
            console.log('[MG] loadFrames: nothing at', key, '| all mg_ keys:', mgKeys);
            return;
        }
        var parsed = JSON.parse(raw);
        if (!parsed || parsed.v !== MG_STORE_VER || !Array.isArray(parsed.frames) || !parsed.frames.length) {
            console.log('[MG] loadFrames: bad/empty data, clearing'); localStorage.removeItem(key); return;
        }
        MG.frames = parsed.frames.map(function(f,i){ return Object.assign({},f,{idx:i,rawData:null}); });
        console.log('[MG] Restored '+MG.frames.length+' frames from '+key);
        showFrameToast('Restored '+MG.frames.length+' frame'+(MG.frames.length!==1?'s':'')+' from last session');
    } catch(e) {
        console.warn('[MG] loadFrames failed:', e);
    }
}

function clearStoredFrames() {
    try {
        var sid = MG.sessionId || '';
        var k = _frameKey(sid);
        if (!k) { try { k = 'mg_frames_'+(localStorage.getItem(MG_PTR_KEY)||''); } catch(_){} }
        if (k) localStorage.removeItem(k);
        localStorage.removeItem(MG_PTR_KEY);
    } catch(_) {}
}


function destroyWin(){
    cancelAnimationFrame(MG.animFrame);
    window.removeEventListener('resize',resize);
    if(MG._ro){MG._ro.disconnect();MG._ro=null;}
    document.getElementById('mg-win')?.remove();
    document.getElementById('mg-detail')?.remove();
    document.getElementById('mg-expand')?.remove();
    document.getElementById('mg-ctx-tray')?.remove();
    document.getElementById('mg-theme-vars')?.remove();
    document.getElementById('mg-frame-toast')?.remove();
    MG.canvas=null;MG.ctx=null;MG.simRunning=false;
}
function makeDrag(el,handle){
    let ox=0,oy=0,sx=0,sy=0,on=false;
    handle.addEventListener('mousedown',e=>{if(['BUTTON','INPUT'].includes(e.target.tagName))return;
        on=true;sx=e.clientX;sy=e.clientY;const r=el.getBoundingClientRect();ox=r.left;oy=r.top;});
    document.addEventListener('mousemove',e=>{if(!on)return;
        el.style.left=(ox+e.clientX-sx)+'px';el.style.top=(oy+e.clientY-sy)+'px';
        el.style.right='auto';el.style.bottom='auto';});
    document.addEventListener('mouseup',()=>{on=false;});
}

// ─── Global controls ───────────────────────────────────────────────────
window.MG_mode=m=>{
    MG.mode=m;MG.showSemantic=m!=='graph';MG.showGraph=m!=='semantic';
    document.querySelectorAll('.mg-mb').forEach(b=>b.classList.remove('mg-on'));
    document.querySelector(`.mg-mb[onclick*="'${m}'"]`)?.classList.add('mg-on');
    updateAlpha();simReheat();
};
window.MG_limit=v=>{
    MG.nodeLimit=v;document.getElementById('mg-nv').textContent=v;
    if(MG.nodes.size>v){
        [...MG.nodes.entries()].sort((a,b)=>a[1].score-b[1].score)
            .slice(0,MG.nodes.size-v).forEach(([id])=>MG.nodes.delete(id));
        MG.edges=MG.edges.filter(e=>MG.nodes.has(e.from)&&MG.nodes.has(e.to));
    }
};
window.MG_thresh=v=>{MG.focusThreshold=v;document.getElementById('mg-tv').textContent=(v*100|0)+'%';updateAlpha();};
window.MG_reset=()=>{MG.pan={x:0,y:0};MG.zoom=1;};
window.MG_clear=()=>{
    MG.nodes.clear();MG.edges=[];MG.selected=null;MG.hovered=null;
    MG.injectedContext.clear();closeExpandPanel();hideDetail();renderCtxTray();
    MG.frames=[];MG.activeFrameIdx=-1;MG.sessionView=false;
    clearStoredFrames();
    renderFrameBar();
};
window.MG_close=()=>{MG.open=false;destroyWin();document.getElementById('mg-open-btn')?.classList.remove('active');};
window.MG_showExpand=id=>{const n=MG.nodes.get(id);if(n)showExpandPanel(n);};
window.MG_pin=id=>{const n=MG.nodes.get(id);if(!n)return;n.fx=n.fx===null?n.x:null;n.fy=n.fy===null?n.y:null;};
window.MG_hide=id=>{MG.nodes.delete(id);MG.edges=MG.edges.filter(e=>e.from!==id&&e.to!==id);hideDetail();};
window.closeExpandPanel=closeExpandPanel;
window.MG_clearStoredFrames=()=>{ clearStoredFrames(); console.log('[MG] Stored frames cleared'); };

// ─── Integration ───────────────────────────────────────────────────────
// Two-tier context update model:
//
//   LIVE PREVIEW  — while the user is typing, the CI poller fires context
//                   previews. These update the graph visually (debounced,
//                   1200ms) but do NOT capture a frame. They are discarded
//                   if a newer preview arrives before the timer fires.
//                   Marked with MG.livePreview=true and shown in the HUD.
//
//   COMMITTED     — when the WS fires 'complete' (message sent, response
//                   received), that context is the ground truth for what
//                   the LLM actually saw. This DOES capture a permanent
//                   frame and clears the live-preview flag.
//
// This means:
//   • Typing fast never creates junk frames
//   • Each completed exchange gets exactly one frame
//   • The live graph still animates while typing (good for exploring context)

function openWith(data) {
    if(!MG.open){MG.open=true;createWin();document.getElementById('mg-open-btn')?.classList.add('active');}
    if(data){
        MG.currentQuery=data._query||'';
        MG.sessionId=data._sessionId||window.app?.sessionId||'';
        ingestLive(data);
    }
}

function _hookThemeManager(){
    const tm=window.themeManager;if(!tm||tm._mgHooked)return;
    tm._mgHooked=true;tm.onChange(()=>{applyTheme();rebuildLegend();});
}

// ── Live preview (debounced, typing) ─────────────────────────────────
let _liveDebounceTimer = null;
let _liveInflightId    = 0;  // increments on every keystroke — stale fetches are dropped

function ingestLive(raw) {
    // Update the graph for preview — no frame capture
    if (!MG.open || !raw) return;
    MG.livePreview = true;
    MG.currentQuery = raw._query || MG.currentQuery;
    MG.sessionId    = raw._sessionId || window.app?.sessionId || MG.sessionId;
    ingestContext(raw, /*isCommit=*/false);
}

function ingestCommit(raw) {
    // A real completed exchange — update graph AND capture frame
    if (!MG.open || !raw) return;
    MG.livePreview = false;
    MG.currentQuery = raw._query || MG.currentQuery;
    MG.sessionId    = raw._sessionId || window.app?.sessionId || MG.sessionId;
    ingestContext(raw, /*isCommit=*/true);
}

// ── Debounced typing hook ─────────────────────────────────────────────
// Patches CI_refreshContext so typing debounces to 1200ms.
// Any in-flight fetch from a previous keystroke is discarded via _liveInflightId.
const LIVE_DEBOUNCE_MS = 1200;

const _ciPatch=setInterval(()=>{
    if(window._CI&&!window._CI._mgP){
        window._CI._mgP=true;
        const origRefresh=window.CI_refreshContext;
        if(origRefresh){
            window.CI_refreshContext=async function(){
                const r=await origRefresh.apply(this,arguments);
                // CI refresh fired — schedule a debounced live update
                if(window._CI?.pendingContext&&MG.open){
                    const myId=++_liveInflightId;
                    clearTimeout(_liveDebounceTimer);
                    const snapCtx={...window._CI.pendingContext,
                        _query:document.getElementById('messageInput')?.value?.trim()||'',
                        _sessionId:window.app?.sessionId||''};
                    _liveDebounceTimer=setTimeout(()=>{
                        if(myId===_liveInflightId) ingestLive(snapCtx);
                    }, LIVE_DEBOUNCE_MS);
                }
                return r;
            };
        }
        clearInterval(_ciPatch);
    }
},300);

// Fallback poller for when CI_refreshContext isn't patchable
let _lastCtxTs=0;
setInterval(()=>{
    if(!MG.open||!window._CI?.pendingContext) return;
    const ctx=window._CI.pendingContext;
    const ts=ctx.elapsed_ms||0;
    if(ts!==_lastCtxTs){
        _lastCtxTs=ts;
        const inputEl=document.getElementById('messageInput');
        const q=(inputEl?.value||'').trim();
        const snapCtx={...ctx,_query:q,_sessionId:window.app?.sessionId||''};
        // If input is empty, a response just landed — treat as commit so frame is captured
        if(!q){
            clearTimeout(_liveDebounceTimer);
            _liveInflightId++;
            ingestCommit(snapCtx);
        } else {
            const myId=++_liveInflightId;
            clearTimeout(_liveDebounceTimer);
            _liveDebounceTimer=setTimeout(()=>{
                if(myId===_liveInflightId) ingestLive(snapCtx);
            }, LIVE_DEBOUNCE_MS);
        }
    }
},400);

// ── WS complete hook — this is the commit ────────────────────────────
if(window.VeraChat){
    const _o=VeraChat.prototype.handleWebSocketMessage;
    VeraChat.prototype.handleWebSocketMessage=function(data){
        if(data?.type==='complete'&&MG.open){
            // Cancel any pending live preview — the commit supersedes it
            clearTimeout(_liveDebounceTimer);
            _liveInflightId++;
            if(data.context_used){
                // Backend sent context_used — ideal path
                ingestCommit({...data.context_used,
                    _query:data.query||MG.currentQuery||'',
                    _sessionId:window.app?.sessionId||''});
            } else if(MG._pendingRawData){
                // Backend didn't send context_used — commit whatever the last live
                // preview ingested. This ensures a frame is always captured per turn.
                ingestCommit({...MG._pendingRawData,
                    _query:data.query||MG.currentQuery||'',
                    _sessionId:window.app?.sessionId||''});
            }
        }
        return _o?.call(this,data);
    };
}

// ─── Toolbar button ────────────────────────────────────────────────────
function installBtn(){
    const bar=document.querySelector('.control-group-sleek');
    if(!bar||document.getElementById('mg-open-btn')) return;
    const btn=document.createElement('button');
    btn.id='mg-open-btn';btn.className='ctrl-btn';btn.title='Memory Graph Explorer';
    btn.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="5" r="2.4"/><circle cx="4" cy="19" r="2.4"/><circle cx="20" cy="19" r="2.4"/>
      <line x1="12" y1="7.4" x2="5.2" y2="16.8"/><line x1="12" y1="7.4" x2="18.8" y2="16.8"/>
      <line x1="6.4" y1="19" x2="17.6" y2="19"/>
    </svg>`;
    btn.onclick=()=>{
        if(MG.open){MG_close();return;}
        const ctx=window._CI?.pendingContext;
        openWith(ctx?{...ctx,
            _query:document.getElementById('messageInput')?.value?.trim()||'',
            _sessionId:window.app?.sessionId||''}:null);
        setTimeout(()=>{
            const q=document.getElementById('messageInput')?.value?.trim();
            const sid=window.app?.sessionId;
            if(q&&sid&&window.fetchContextPreview)
                window.fetchContextPreview(sid,q).then(d=>{if(d&&MG.open)ingestContext({...d,_query:q,_sessionId:sid});});
            else if(window._CI?.pendingContext&&MG.open)
                ingestContext({...window._CI.pendingContext,_sessionId:sid||''});
        },100);
    };
    document.getElementById('ci-panel-btn')?.after(btn)||bar.appendChild(btn);
}

// ─── Helpers ───────────────────────────────────────────────────────────
function hash(s){let h=0;for(let i=0;i<s.length;i++)h=(Math.imul(31,h)+s.charCodeAt(i))|0;return Math.abs(h).toString(36);}
function textSim(a,b){
    const wa=new Set((a||'').toLowerCase().split(/\W+/).filter(w=>w.length>3));
    const wb=new Set((b||'').toLowerCase().split(/\W+/).filter(w=>w.length>3));
    if(!wa.size||!wb.size)return 0;
    let n=0;for(const w of wa)if(wb.has(w))n++;
    return n/Math.sqrt(wa.size*wb.size);
}
function srcType(s){
    if(!s)return'default';
    if(s.includes('session'))return'query';
    if(s.includes('longterm'))return'document';
    if(s.includes('graph'))return'entity';
    if(s.includes('recalled'))return'recalled_exchange';
    return'default';
}
function lighten(h,a){const c=parseInt(h.slice(1),16);return'#'+[c>>16,(c>>8)&0xff,c&0xff].map(v=>Math.min(255,v+a).toString(16).padStart(2,'0')).join('');}
function rrect(ctx,x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.arcTo(x+w,y,x+w,y+r,r);ctx.lineTo(x+w,y+h-r);ctx.arcTo(x+w,y+h,x+w-r,y+h,r);ctx.lineTo(x+r,y+h);ctx.arcTo(x,y+h,x,y+h-r,r);ctx.lineTo(x,y+r);ctx.arcTo(x,y,x+r,y,r);ctx.closePath();}
function escH(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ─── Debug ─────────────────────────────────────────────────────────────
window._MG=MG;
window._MG.debugIngest=data=>{MG_clear();openWith(data);};
window._MG.dump=()=>({
    nodes:[...MG.nodes.values()].map(n=>({id:n.id,text:n.text.slice(0,40),score:n.score,type:n.type,source:n.source})),
    edges:MG.edges.length,
    frames:MG.frames.length,
    injected:[...MG.injectedContext.keys()],
});
window._MG.reloadTheme=()=>{applyTheme();rebuildLegend();};
window._MG.dumpFrames=()=>MG.frames.map(f=>({
    idx:f.idx, label:f.label, ts:new Date(f.ts).toISOString(),
    retrievedNodes:f.nodeCount, historyNodes:f.historyCount||0,
    sources:[...new Set(f.nodeSnap.map(n=>n.source))],
}));
/** Show which nodes are shared vs unique between two frames */
window._MG.frameDiff=(a,b)=>{
    const fa=MG.frames[a]; const fb=MG.frames[b];
    if(!fa||!fb){console.error('Invalid frame indices');return;}
    const ia=new Set(fa.nodeSnap.map(n=>n.id));
    const ib=new Set(fb.nodeSnap.map(n=>n.id));
    const shared=[...ia].filter(id=>ib.has(id));
    const onlyA=[...ia].filter(id=>!ib.has(id));
    const onlyB=[...ib].filter(id=>!ia.has(id));
    const sim=_fpSimilarity(fa._fp,fb._fp);
    console.group(`Frame ${a+1} vs Frame ${b+1}  (${(sim*100).toFixed(0)}% similar)`);
    console.log(`Shared (${shared.length}):`,shared.map(id=>fa.nodeSnap.find(n=>n.id===id)?.text?.slice(0,50)));
    console.log(`Only in F${a+1} (${onlyA.length}):`,onlyA.map(id=>fa.nodeSnap.find(n=>n.id===id)?.text?.slice(0,50)));
    console.log(`Only in F${b+1} (${onlyB.length}):`,onlyB.map(id=>fb.nodeSnap.find(n=>n.id===id)?.text?.slice(0,50)));
    console.groupEnd();
    return {shared,onlyA,onlyB,similarity:sim};
};
/** Show what sources are present across all frames — helps diagnose if backend is growing context */
window._MG.frameSourceBreakdown=()=>{
    return MG.frames.map(f=>{
        const counts={};
        for(const n of f.nodeSnap) counts[n.source]=(counts[n.source]||0)+1;
        return {frame:f.idx+1,query:f.label.slice(0,40),counts};
    });
};

// ─── CSS ───────────────────────────────────────────────────────────────
if(!document.getElementById('mg-css')){
    const s=document.createElement('style');s.id='mg-css';s.textContent=`
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
#mg-win{position:fixed;bottom:20px;left:20px;width:760px;height:580px;z-index:9400;display:flex;flex-direction:column;background:#07111e;border:1px solid #152236;border-radius:10px;overflow:hidden;box-shadow:0 0 0 1px rgba(59,130,246,.06),0 28px 70px rgba(0,0,0,.75);font-family:'JetBrains Mono',ui-monospace,monospace;animation:mg-in .28s cubic-bezier(.34,1.56,.64,1);resize:both;min-width:480px;min-height:380px}
@keyframes mg-in{from{opacity:0;transform:scale(.9) translateY(16px)}to{opacity:1;transform:none}}
#mg-bar{display:flex;align-items:center;gap:8px;padding:7px 11px;background:#0b1929;border-bottom:1px solid #152236;cursor:move;user-select:none;flex-shrink:0}
.mg-logo{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;letter-spacing:1.4px;color:#3b82f6;white-space:nowrap}
#mg-modes{display:flex;gap:2px}
.mg-mb{display:flex;align-items:center;gap:3px;padding:3px 8px;background:transparent;border:1px solid #152236;border-radius:4px;color:#334155;font-family:inherit;font-size:10px;cursor:pointer;transition:all .15s;white-space:nowrap}
.mg-mb:hover{color:#64748b;border-color:#1e3a5f}
.mg-on{background:rgba(59,130,246,.1)!important;border-color:rgba(59,130,246,.4)!important;color:#3b82f6!important}
#mg-ctrls{display:flex;align-items:center;gap:7px;margin-left:auto}
.mg-lbl{display:flex;align-items:center;gap:4px;color:#334155;font-size:10px;cursor:pointer;white-space:nowrap}
.mg-sl{width:55px;accent-color:#3b82f6;cursor:pointer}
.mg-lbl span{font-size:10px;color:#3b82f6;font-weight:700;min-width:24px;text-align:center}
.mg-btn{padding:3px 7px;background:transparent;border:1px solid #152236;border-radius:4px;color:#334155;font-family:inherit;font-size:10px;cursor:pointer;transition:all .15s;white-space:nowrap}
.mg-btn:hover{border-color:#1e3a5f;color:#64748b}
.mg-bx:hover{border-color:#ef4444!important;color:#ef4444!important}
#mg-wrap{flex:1;position:relative;overflow:hidden;background:radial-gradient(ellipse at 35% 40%,#091525 0%,#050d18 100%)}
#mg-cv{display:block;width:100%;height:100%;cursor:grab}
#mg-leg{display:flex;align-items:center;gap:9px;padding:5px 12px;background:#0b1929;border-top:1px solid #152236;flex-shrink:0;flex-wrap:wrap}
.mg-li{display:flex;align-items:center;gap:4px;font-size:9px;color:#334155;white-space:nowrap}
.mg-li i{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.mg-sep{width:1px;height:11px;background:#152236;margin:0 2px}
.mg-el{width:16px;height:0;border-top-width:1.5px;border-top-style:solid;display:inline-block}
#mg-hint{padding:3px 12px;font-size:9px;color:#152236;letter-spacing:.4px;flex-shrink:0;text-align:center}

/* ── Frame bar ── */
#mg-frame-bar{background:#0b1929;border-top:1px solid #152236;flex-shrink:0;font-family:'JetBrains Mono',ui-monospace,monospace}
.mg-frame-thumb{display:flex;flex-direction:column;gap:2px;padding:5px 7px;border:1px solid #152236;border-radius:5px;cursor:pointer;min-width:80px;max-width:110px;transition:border-color .15s,box-shadow .15s;flex-shrink:0}
.mg-frame-thumb:hover{border-color:#3b82f655}
.mg-frame-thumb.active{border-color:#3b82f6;box-shadow:0 0 0 1px #3b82f644}
.mg-ft-num{font-size:9px;font-weight:700;letter-spacing:.6px}
.mg-ft-bar{height:3px;border-radius:2px;overflow:hidden;width:100%}
.mg-ft-q{font-size:8px;color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.3}
.mg-ft-ts{font-size:7px;color:#1a3050;letter-spacing:.3px}
.mg-fbar-btn{padding:3px 7px;background:transparent;border:1px solid #152236;border-radius:4px;color:#334155;font-family:inherit;font-size:9px;cursor:pointer;transition:all .15s;white-space:nowrap}
.mg-fbar-btn:hover{border-color:#3b82f655;color:#3b82f6}
.mg-fbar-btn.mg-on{background:#3b82f61a;border-color:#3b82f666;color:#3b82f6}
#mg-ft-scroll::-webkit-scrollbar{height:3px}
#mg-ft-scroll::-webkit-scrollbar-track{background:transparent}
#mg-ft-scroll::-webkit-scrollbar-thumb{background:#152236;border-radius:2px}

/* ── Toast ── */
#mg-frame-toast{position:fixed;bottom:28px;right:20px;z-index:9900;padding:7px 14px;background:#0b1929;border:1px solid #10b98155;color:#10b981;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10px;border-radius:6px;pointer-events:none;transition:opacity .4s;opacity:0}

.mg-detail{position:fixed;width:275px;background:#0b1929;border:1px solid #1e3a5f;border-radius:8px;box-shadow:0 10px 40px rgba(0,0,0,.65),0 0 0 1px rgba(59,130,246,.08);z-index:9700;padding:12px;font-family:'JetBrains Mono',ui-monospace,monospace;display:none;animation:mg-din .14s ease}
@keyframes mg-din{from{opacity:0;transform:scale(.93)}to{opacity:1;transform:none}}
.mg-da-btn{padding:4px 0;background:transparent;border:1px solid #152236;border-radius:4px;color:#3b82f6;font-family:inherit;font-size:10px;cursor:pointer;transition:all .15s;flex:1}
.mg-da-btn:hover{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.4)}
#mg-expand{position:fixed;width:330px;background:#0b1929;border:1px solid #1e3a5f;border-radius:8px;box-shadow:0 16px 48px rgba(0,0,0,.75);z-index:9800;font-family:'JetBrains Mono',ui-monospace,monospace;display:none;animation:mg-din .16s ease;overflow:hidden}
#mg-expand .mg-ep-hdr{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;font-size:10px;font-weight:700;letter-spacing:.5px;cursor:default}
#mg-expand .mg-ep-body{max-height:300px;overflow-y:auto}
#mg-expand .mg-ep-list{padding:0 0 4px}
#mg-expand .mg-ep-item{padding:7px 10px;cursor:pointer;transition:background .1s}
#mg-expand .mg-ep-type{font-size:8px;opacity:.6}
#mg-expand .mg-ep-score{font-size:9px;font-weight:700}
#mg-expand .mg-ep-text{font-size:10px;line-height:1.4;margin-top:2px;word-break:break-word}
#mg-expand .mg-ep-footer{display:flex;gap:6px;padding:8px 10px;flex-wrap:wrap}
#mg-expand .mg-ep-add-btn,#mg-expand .mg-ep-inject-btn,#mg-expand .mg-ep-cancel{padding:5px 10px;border:none;border-radius:4px;font-family:inherit;font-size:10px;cursor:pointer;transition:filter .15s;white-space:nowrap;font-weight:600}
#mg-expand .mg-ep-cancel{background:transparent;border:1px solid #152236}
#mg-ctx-tray{position:fixed;bottom:4px;left:50%;transform:translateX(-50%);z-index:9600;padding:7px 12px;border-radius:8px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10px;display:none;max-width:90vw;box-shadow:0 4px 24px rgba(0,0,0,.6)}
.mg-ct-label{font-weight:700;white-space:nowrap;flex-shrink:0}
.mg-ct-chip{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:12px;font-size:9px;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mg-ct-chip-x{background:none;border:none;cursor:pointer;font-size:12px;line-height:1;padding:0;flex-shrink:0}
.mg-ct-send-btn,.mg-ct-clear{padding:4px 10px;border-radius:4px;font-family:inherit;font-size:10px;cursor:pointer;font-weight:700;white-space:nowrap;flex-shrink:0;transition:filter .15s}
.mg-ct-clear{background:transparent;border:1px solid #152236}
    `;document.head.appendChild(s);
}

// ─── Bootstrap ─────────────────────────────────────────────────────────
const _boot=setInterval(()=>{
    if(document.querySelector('.control-group-sleek')||document.getElementById('ci-panel-btn')){
        clearInterval(_boot);
        installBtn();
        _hookThemeManager();
        if(!window.themeManager){
            const _tmWait=setInterval(()=>{if(window.themeManager){clearInterval(_tmWait);_hookThemeManager();applyTheme();}},400);
        }
        console.log('✅ Memory Graph Explorer v6.0 (Frames) ready');
    }
},200);

})();