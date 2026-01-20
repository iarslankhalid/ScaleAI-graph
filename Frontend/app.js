/**
 * ScaleAI GraphRAG Dashboard
 * Interactive graph visualization and query interface
 */

// ===========================================
// Configuration
// ===========================================

const API_BASE_URL = 'http://localhost:8000';

const TIER_COLORS = {
    0: '#9333ea',  // Purple - Control
    1: '#22c55e',  // Green - Input
    2: '#3b82f6',  // Blue - Monthly
    3: '#f59e0b',  // Amber - Annual
    4: '#ef4444',  // Red - Goals
    5: '#ec4899',  // Pink - Macro
    '-1': '#06b6d4' // Cyan - Concept
};

const NODE_SHAPES = {
    'FIELD': 'dot',
    'CONCEPT': 'diamond'
};

const HIGHLIGHT_COLOR = '#fbbf24';

// ===========================================
// State
// ===========================================

let network = null;
let nodesDataset = null;
let edgesDataset = null;
let allNodes = [];
let allEdges = [];
let selectedNodeId = null;
let highlightedNodes = new Set();
let highlightedEdges = new Set();

// ===========================================
// Initialize
// ===========================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    console.log('🚀 Initializing ScaleAI GraphRAG Dashboard...');
    
    // Setup event listeners
    setupEventListeners();
    
    // Load graph data
    await loadGraphData();
    
    // Load stats
    await loadGraphStats();
    
    showToast('Dashboard loaded successfully!', 'success');
}

// ===========================================
// Event Listeners
// ===========================================

function setupEventListeners() {
    // Query button
    document.getElementById('btn-query').addEventListener('click', executeQuery);
    
    // Query input enter key
    document.getElementById('query-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') executeQuery();
    });
    
    // Node search
    document.getElementById('node-search').addEventListener('input', debounce(searchNodes, 300));
    
    // Tier filters
    document.querySelectorAll('.tier-checkbox input').forEach(checkbox => {
        checkbox.addEventListener('change', filterGraph);
    });
    
    // Control buttons
    document.getElementById('btn-reset-view').addEventListener('click', resetView);
    document.getElementById('btn-fit-graph').addEventListener('click', fitGraph);
    document.getElementById('btn-clear-highlight').addEventListener('click', clearHighlights);
    
    // Node detail buttons
    document.getElementById('btn-show-upstream').addEventListener('click', () => showTraversal('upstream'));
    document.getElementById('btn-show-downstream').addEventListener('click', () => showTraversal('downstream'));
    
    // Context tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
}

// ===========================================
// API Functions
// ===========================================

async function loadGraphStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/graph/stats`);
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        
        document.getElementById('stat-nodes').textContent = stats.total_nodes || 0;
        document.getElementById('stat-edges').textContent = stats.total_edges || 0;
        document.getElementById('stat-fields').textContent = stats.nodes_by_type?.FIELD || 0;
        document.getElementById('stat-concepts').textContent = stats.nodes_by_type?.CONCEPT || 0;
        
    } catch (error) {
        console.error('Error loading stats:', error);
        showToast('Failed to load graph statistics', 'error');
    }
}

async function loadGraphData() {
    const loading = document.getElementById('graph-loading');
    const loadingText = document.getElementById('loading-text');
    
    loading.classList.remove('hidden');
    if (loadingText) loadingText.textContent = 'Fetching graph data...';
    
    try {
        // Fetch graph data - limit to 500 nodes for better performance
        const nodesResponse = await fetch(`${API_BASE_URL}/api/graph/export?limit=500`);
        
        if (!nodesResponse.ok) {
            throw new Error('Export endpoint failed');
        }
        
        const graphData = await nodesResponse.json();
        console.log(`📊 Loaded ${graphData.total_nodes} nodes and ${graphData.total_edges} edges`);
        
        if (loadingText) loadingText.textContent = 'Initializing visualization...';
        processGraphData(graphData);
        
    } catch (error) {
        console.error('Error loading graph:', error);
        showToast('Failed to load graph. Is the API running?', 'error');
        loading.classList.add('hidden');
        // Initialize empty network
        allNodes = [];
        allEdges = [];
        initializeNetwork();
    }
    // Note: loading indicator is hidden after stabilization completes
}

async function loadGraphViaSearch() {
    try {
        // Get some initial nodes by searching common terms
        const searchTerms = ['property', 'loan', 'cashflow', 'income', 'expense', 'lvr', 'debt'];
        const nodeMap = new Map();
        const edges = [];
        
        for (const term of searchTerms) {
            try {
                const response = await fetch(`${API_BASE_URL}/api/graph/search`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: term, limit: 100 })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    data.results?.forEach(node => {
                        nodeMap.set(node.id, node);
                    });
                }
            } catch (e) {
                console.warn(`Search for "${term}" failed:`, e);
            }
        }
        
        // Convert to arrays
        allNodes = Array.from(nodeMap.values());
        allEdges = edges;
        
        if (allNodes.length === 0) {
            showToast('No graph data found. Please ensure the API is running and data is loaded.', 'warning');
        }
        
        initializeNetwork();
        
    } catch (error) {
        console.error('Error in fallback graph loading:', error);
        showToast('Failed to load graph data', 'error');
        initializeNetwork(); // Initialize empty network
    }
}

function processGraphData(data) {
    allNodes = data.nodes || [];
    allEdges = data.edges || [];
    initializeNetwork();
}

async function executeQuery() {
    const queryInput = document.getElementById('query-input');
    const query = queryInput.value.trim();
    
    if (!query) {
        showToast('Please enter a query', 'warning');
        return;
    }
    
    const maxDepth = parseInt(document.getElementById('max-depth').value) || 3;
    
    // Show loading state
    document.getElementById('context-placeholder').style.display = 'none';
    document.getElementById('context-content').style.display = 'flex';
    document.getElementById('answer-text').innerHTML = '<div class="spinner" style="width:20px;height:20px;"></div> Processing query...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                max_depth: maxDepth
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Query failed');
        }
        
        const result = await response.json();
        displayQueryResult(result);
        
        // Highlight the traversal path on the graph
        highlightQueryPath(result);
        
        showToast('Query completed!', 'success');
        
    } catch (error) {
        console.error('Query error:', error);
        document.getElementById('answer-text').innerHTML = `<span style="color: var(--accent-danger)">Error: ${error.message}</span>`;
        showToast(`Query failed: ${error.message}`, 'error');
    }
}

async function fetchNodeDetails(nodeId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/graph/node/${encodeURIComponent(nodeId)}`);
        if (!response.ok) throw new Error('Node not found');
        return await response.json();
    } catch (error) {
        console.error('Error fetching node:', error);
        return null;
    }
}

async function fetchTraversal(nodeId, direction, maxDepth = 3) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/graph/traverse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: nodeId,
                direction: direction,
                max_depth: maxDepth
            })
        });
        
        if (!response.ok) throw new Error('Traversal failed');
        return await response.json();
        
    } catch (error) {
        console.error('Traversal error:', error);
        return null;
    }
}

// ===========================================
// Network Visualization
// ===========================================

function initializeNetwork() {
    const container = document.getElementById('graph-canvas');
    
    if (!container) {
        console.error('❌ Graph canvas container not found!');
        return;
    }
    
    // Check container dimensions
    const rect = container.getBoundingClientRect();
    console.log(`📐 Canvas dimensions: ${rect.width}x${rect.height}`);
    
    if (rect.width === 0 || rect.height === 0) {
        console.error('❌ Canvas has zero dimensions! Check CSS layout.');
        showToast('Graph canvas has no size. Check browser console.', 'error');
        return;
    }
    
    console.log(`🔧 Initializing network with ${allNodes.length} nodes and ${allEdges.length} edges`);
    
    if (allNodes.length === 0) {
        console.warn('⚠️ No nodes to display!');
        showToast('No graph nodes available', 'warning');
        document.getElementById('graph-loading').classList.add('hidden');
        return;
    }
    
    // Prepare nodes
    const nodes = allNodes.map(node => ({
        id: node.id,
        label: truncateLabel(node.label || node.id),
        // title removed - we use custom popup instead of vis.js tooltip
        color: getNodeColor(node),
        shape: NODE_SHAPES[node.type] || 'dot',
        size: getNodeSize(node),
        font: {
            color: '#e4e6eb',
            size: 10
        },
        tier: node.tier,
        type: node.type,
        originalColor: getNodeColor(node),
        data: node
    }));
    
    // Prepare edges
    const edges = allEdges.map((edge, idx) => ({
        id: `edge-${idx}`,
        from: edge.source || edge.from,
        to: edge.target || edge.to,
        arrows: 'to',
        color: {
            color: '#30363d',
            highlight: HIGHLIGHT_COLOR,
            opacity: 0.6
        },
        width: 1,
        type: edge.type
    }));
    
    console.log(`📊 Prepared ${nodes.length} vis nodes and ${edges.length} vis edges`);
    
    // Check if vis is available
    if (typeof vis === 'undefined') {
        console.error('❌ vis.js library not loaded!');
        showToast('Visualization library failed to load', 'error');
        document.getElementById('graph-loading').classList.add('hidden');
        return;
    }
    
    try {
        console.log('🎨 Creating vis.DataSets...');
        nodesDataset = new vis.DataSet(nodes);
        edgesDataset = new vis.DataSet(edges);
        console.log('✅ DataSets created');
        
        const data = {
            nodes: nodesDataset,
            edges: edgesDataset
        };
        
        const options = {
            nodes: {
                borderWidth: 2,
                borderWidthSelected: 3,
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.3)',
                    size: 8,
                    x: 2,
                    y: 2
                },
                font: {
                    color: '#e4e6eb',
                    size: 12,
                    face: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto'
                }
            },
            edges: {
                smooth: {
                    enabled: true,
                    type: 'curvedCW',
                    roundness: 0.2
                },
                arrows: {
                    to: {
                        enabled: false
                    }
                },
                color: {
                    color: 'rgba(48, 54, 61, 0.4)',
                    highlight: '#fbbf24',
                    hover: 'rgba(88, 166, 255, 0.5)'
                },
                width: 1,
                selectionWidth: 2,
                hoverWidth: 2
            },
            physics: {
                enabled: true,
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {
                    gravitationalConstant: -150,
                    centralGravity: 0.02,
                    springLength: 150,
                    springConstant: 0.08,
                    damping: 0.6,
                    avoidOverlap: 0.8
                },
                stabilization: {
                    enabled: true,
                    iterations: 1000,
                    updateInterval: 50,
                    fit: true
                },
                maxVelocity: 50,
                minVelocity: 0.75,
                timestep: 0.5
            },
            interaction: {
                hover: true,
                tooltipDelay: 100,
                zoomView: true,
                dragView: true,
                navigationButtons: false,
                keyboard: {
                    enabled: true,
                    bindToWindow: false
                },
                hideEdgesOnDrag: true,
                hideEdgesOnZoom: false,
                tooltip: false  // Disable default vis.js tooltip (we use custom popup)
            },
            layout: {
                improvedLayout: true,
                randomSeed: 42
            }
        };
        
        console.log('🎨 Creating vis.Network instance...');
        network = new vis.Network(container, data, options);
        console.log('✅ Network object created successfully');

        // Create custom popup div
        let popupDiv = document.getElementById('network-popup');
        if (!popupDiv) {
            popupDiv = document.createElement('div');
            popupDiv.id = 'network-popup';
            popupDiv.className = 'network-popup';
            document.body.appendChild(popupDiv);
        }

        // Event handlers
        network.on('selectNode', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                selectNode(nodeId);
            }
        });

        network.on('deselectNode', () => {
            clearNodeSelection();
        });

        network.on('doubleClick', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                focusOnNode(nodeId);
            }
        });

        // Custom hover popup
        network.on('hoverNode', (params) => {
            const nodeId = params.node;
            const node = nodesDataset.get(nodeId);
            if (node && node.data) {
                showNodePopup(params.event, node.data);
            }
        });

        network.on('blurNode', () => {
            hideNodePopup();
        });

        // Hide popup when dragging
        network.on('dragStart', () => {
            hideNodePopup();
        });
        
        // Stabilization done
        network.on('stabilizationIterationsDone', () => {
            console.log('✅ Network stabilization complete');

            // Keep physics enabled but reduce it
            network.setOptions({
                physics: {
                    enabled: true,
                    forceAtlas2Based: {
                        gravitationalConstant: -50,
                        centralGravity: 0.005,
                        springLength: 150,
                        springConstant: 0.02,
                        damping: 0.9
                    }
                }
            });

            // Hide loading indicator
            document.getElementById('graph-loading').classList.add('hidden');

            // Fit the graph to view after stabilization
            network.fit({
                animation: {
                    duration: 800,
                    easingFunction: 'easeInOutQuad'
                }
            });
        });
        
        // Stabilization progress
        network.on('stabilizationProgress', (params) => {
            const progress = Math.round((params.iterations / params.total) * 100);
            
            // Update progress bar
            const progressBar = document.getElementById('progress-bar');
            const progressFill = document.getElementById('progress-fill');
            const loadingText = document.getElementById('loading-text');
            
            if (progressBar && progressFill) {
                progressBar.style.display = 'block';
                progressFill.style.width = `${progress}%`;
            }
            if (loadingText) {
                loadingText.textContent = `Laying out graph... ${progress}%`;
            }
            
            if (progress % 20 === 0) {
                console.log(`⏳ Stabilizing: ${progress}%`);
            }
        });
        
        console.log(`✅ Network initialized successfully!`);
        
    } catch (error) {
        console.error('❌ Failed to initialize network:', error);
        console.error('Error stack:', error.stack);
        showToast(`Failed to initialize graph: ${error.message}`, 'error');
        document.getElementById('graph-loading').classList.add('hidden');
    }
}

function getNodeColor(node) {
    const tier = node.tier !== undefined ? node.tier : -1;
    return TIER_COLORS[tier] || TIER_COLORS['-1'];
}

function getNodeSize(node) {
    if (node.type === 'CONCEPT') return 18;
    const tier = node.tier !== undefined ? node.tier : 1;
    // Make size differences more subtle and all nodes slightly larger
    return 12 + Math.max(0, (4 - tier)) * 1.5;
}

function truncateLabel(label, maxLength = 20) {
    if (!label) return '...';
    if (label.length <= maxLength) return label;
    return label.substring(0, maxLength) + '...';
}

function createNodeTooltip(node) {
    const tierName = node.tier_name || '';
    const definition = node.definition || node.payload || '';
    const tierText = node.tier >= 0 ? `Tier ${node.tier}${tierName ? ' - ' + tierName : ''}` : 'Concept';

    // Create plain text tooltip for vis.js (it doesn't support HTML)
    let tooltip = `${node.label || node.id}\n`;
    tooltip += `━━━━━━━━━━━━━━━━━━━━\n`;
    tooltip += `Type: ${node.type}  |  ${tierText}\n`;
    if (node.section) {
        tooltip += `Section: ${node.section}\n`;
    }
    if (definition) {
        tooltip += `\n${definition.length > 150 ? definition.substring(0, 150) + '...' : definition}`;
    }

    return tooltip;
}

// ===========================================
// Node Selection & Details
// ===========================================

async function selectNode(nodeId) {
    selectedNodeId = nodeId;
    
    // Get node from dataset or fetch from API
    let nodeData = nodesDataset.get(nodeId)?.data;
    
    if (!nodeData) {
        nodeData = await fetchNodeDetails(nodeId);
    }
    
    if (nodeData) {
        displayNodeDetails(nodeData);
    }
}

function displayNodeDetails(node) {
    document.querySelector('.details-placeholder').style.display = 'none';
    document.getElementById('details-content').style.display = 'block';
    
    document.getElementById('detail-id').textContent = node.id || '-';
    document.getElementById('detail-label').textContent = node.label || '-';
    document.getElementById('detail-type').textContent = node.type || '-';
    document.getElementById('detail-tier').textContent = node.tier >= 0 ? `Tier ${node.tier}: ${node.tier_name || ''}` : 'N/A';
    document.getElementById('detail-section').textContent = node.section || '-';
    document.getElementById('detail-definition').textContent = node.definition || node.payload || 'No description available';
}

function clearNodeSelection() {
    selectedNodeId = null;
    document.querySelector('.details-placeholder').style.display = 'block';
    document.getElementById('details-content').style.display = 'none';
}

// ===========================================
// Query Results Display
// ===========================================

function displayQueryResult(result) {
    // Update confidence
    const confidencePercent = (result.confidence * 100).toFixed(0);
    document.getElementById('confidence-value').textContent = `${confidencePercent}%`;

    // Color code confidence
    const confidenceBadge = document.getElementById('confidence-badge');
    if (result.confidence >= 0.8) {
        confidenceBadge.style.borderLeft = '3px solid var(--accent-secondary)';
    } else if (result.confidence >= 0.5) {
        confidenceBadge.style.borderLeft = '3px solid var(--accent-warning)';
    } else {
        confidenceBadge.style.borderLeft = '3px solid var(--accent-danger)';
    }

    // Update answer (render markdown)
    const answerHtml = marked.parse(result.answer || 'No answer generated');
    document.getElementById('answer-text').innerHTML = answerHtml;

    // Update query metadata
    const debug = result.context_debug;
    document.getElementById('query-text').textContent = result.query || '-';
    document.getElementById('query-type').textContent = debug?.intent?.query_type || '-';
    document.getElementById('query-direction').textContent = debug?.intent?.direction || '-';

    // Update traversal info
    document.getElementById('traversal-target').textContent = result.traversal?.target || debug?.target_node?.label || '-';
    document.getElementById('traversal-direction').textContent = result.traversal?.direction || '-';
    document.getElementById('traversal-visited').textContent = result.traversal?.nodes_visited || 0;
    
    // Update path display
    const pathContainer = document.getElementById('traversal-path');
    pathContainer.innerHTML = '';
    
    if (result.sources) {
        const pathSource = result.sources.find(s => s.type === 'path');
        if (pathSource && pathSource.value) {
            const pathNodes = pathSource.value.split(' → ');
            pathNodes.forEach((nodeName, idx) => {
                const nodeSpan = document.createElement('span');
                nodeSpan.className = 'path-node';
                nodeSpan.textContent = nodeName;
                nodeSpan.addEventListener('click', () => searchAndFocusNode(nodeName));
                pathContainer.appendChild(nodeSpan);
                
                if (idx < pathNodes.length - 1) {
                    const arrow = document.createElement('span');
                    arrow.className = 'path-arrow';
                    arrow.textContent = '→';
                    pathContainer.appendChild(arrow);
                }
            });
        }
    }
    
    // Update thinking process - show step by step what LLM did
    const thinkingContainer = document.getElementById('thinking-steps');
    thinkingContainer.innerHTML = '';

    // Step 1: Intent Analysis
    if (debug?.intent) {
        const step1 = createThinkingStep(
            1,
            'Intent Analysis',
            'Analyzed the question to understand what information is needed',
            `
                <div class="step-detail">Query Type: <strong>${debug.intent.query_type}</strong></div>
                <div class="step-detail">Direction: <strong>${debug.intent.direction}</strong></div>
                ${debug.intent.target_fields?.length > 0 ? `<div class="step-detail">Target Fields: <strong>${debug.intent.target_fields.join(', ')}</strong></div>` : ''}
                <div class="step-detail">Confidence: <strong>${(debug.intent.confidence * 100).toFixed(0)}%</strong></div>
            `,
            'success'
        );
        thinkingContainer.appendChild(step1);
    }

    // Step 2: Graph Traversal
    const targetNode = debug?.target_node;
    if (targetNode) {
        const step2 = createThinkingStep(
            2,
            'Graph Traversal',
            `Found target node "${targetNode.label}" and traversed the graph`,
            `
                <div class="step-detail">Target Node: <strong>${targetNode.label}</strong> (Tier ${targetNode.tier})</div>
                <div class="step-detail">Nodes Explored: <strong>${result.traversal?.nodes_visited || 0}</strong></div>
                <div class="step-detail">Upstream Nodes: <strong>${debug?.upstream_nodes?.length || 0}</strong></div>
                <div class="step-detail">Downstream Nodes: <strong>${debug?.downstream_nodes?.length || 0}</strong></div>
            `,
            'success'
        );
        thinkingContainer.appendChild(step2);
    }

    // Step 3: Context Gathering
    const concepts = debug?.concepts || [];
    const totalContext = (debug?.upstream_nodes?.length || 0) + (debug?.downstream_nodes?.length || 0) + concepts.length;
    if (totalContext > 0) {
        const step3 = createThinkingStep(
            3,
            'Context Gathering',
            'Collected relevant context from the knowledge graph',
            `
                <div class="step-detail">Related Concepts: <strong>${concepts.length}</strong></div>
                <div class="step-detail">Upstream Context: <strong>${debug?.upstream_nodes?.length || 0} nodes</strong></div>
                <div class="step-detail">Downstream Context: <strong>${debug?.downstream_nodes?.length || 0} nodes</strong></div>
                <div class="step-detail">Total Context Items: <strong>${totalContext}</strong></div>
            `,
            'success'
        );
        thinkingContainer.appendChild(step3);
    }

    // Step 4: LLM Generation
    const step4 = createThinkingStep(
        4,
        'Answer Generation',
        'Synthesized the answer using the gathered context',
        `
            <div class="step-detail">Model: <strong>LLM (via API)</strong></div>
            <div class="step-detail">Confidence: <strong>${confidencePercent}%</strong></div>
            <div class="step-detail">Context Used: <strong>${totalContext} items</strong></div>
        `,
        'success'
    );
    thinkingContainer.appendChild(step4);
    
    // Update sources
    const sourcesContainer = document.getElementById('context-sources');
    sourcesContainer.innerHTML = '';
    
    if (result.sources) {
        result.sources.forEach(source => {
            const div = document.createElement('div');
            div.className = 'source-item';
            div.innerHTML = `
                <div class="source-type">${source.type}</div>
                <div>${source.value}</div>
            `;
            sourcesContainer.appendChild(div);
        });
    }
    
    // Update concepts from debug context
    const conceptsContainer = document.getElementById('context-concepts');
    conceptsContainer.innerHTML = '';

    const conceptsList = debug?.concepts || result.sources?.filter(s => s.type === 'concept') || [];
    if (conceptsList.length > 0) {
        conceptsList.forEach(concept => {
            const div = document.createElement('div');
            div.className = 'node-list-item';
            div.innerHTML = `
                <span class="node-tier" style="background: var(--concept);"></span>
                <span class="node-label">${concept.label || concept.value || concept.id}</span>
                ${concept.category ? `<span style="color: var(--text-muted); font-size: 0.7rem;">(${concept.category})</span>` : ''}
            `;
            div.addEventListener('click', () => searchAndFocusNode(concept.id || concept.value));
            conceptsContainer.appendChild(div);
        });
    } else {
        conceptsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No concepts found</div>';
    }
    
    // Update upstream nodes
    const upstreamContainer = document.getElementById('context-upstream');
    upstreamContainer.innerHTML = '';
    
    const upstreamNodes = debug?.upstream_nodes || [];
    if (upstreamNodes.length > 0) {
        upstreamNodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'node-list-item';
            div.innerHTML = `
                <span class="node-tier" style="background: ${TIER_COLORS[node.tier] || TIER_COLORS['-1']};"></span>
                <span class="node-label">${node.label || node.id}</span>
            `;
            div.addEventListener('click', () => searchAndFocusNode(node.id));
            upstreamContainer.appendChild(div);
        });
    } else {
        upstreamContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No upstream nodes</div>';
    }
    
    // Update downstream nodes
    const downstreamContainer = document.getElementById('context-downstream');
    downstreamContainer.innerHTML = '';
    
    const downstreamNodes = debug?.downstream_nodes || [];
    if (downstreamNodes.length > 0) {
        downstreamNodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'node-list-item';
            div.innerHTML = `
                <span class="node-tier" style="background: ${TIER_COLORS[node.tier] || TIER_COLORS['-1']};"></span>
                <span class="node-label">${node.label || node.id}</span>
            `;
            div.addEventListener('click', () => searchAndFocusNode(node.id));
            downstreamContainer.appendChild(div);
        });
    } else {
        downstreamContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No downstream nodes</div>';
    }
    
    // Update LLM prompt
    const llmPrompt = document.getElementById('llm-prompt');
    llmPrompt.textContent = debug?.context_prompt || 'Context prompt not available';
    
    // Update raw JSON with full debug info
    const rawOutput = {
        ...result,
        _frontend_note: "This shows the full response including what context was sent to the LLM"
    };
    document.getElementById('raw-response').textContent = JSON.stringify(rawOutput, null, 2);
    
    // Switch to answer tab
    switchTab('answer');
}

function highlightQueryPath(result) {
    clearHighlights();
    
    const debug = result.context_debug;
    const nodesToHighlight = [];
    
    // Collect all nodes to highlight
    if (debug?.target_node) {
        nodesToHighlight.push(debug.target_node);
    }
    
    if (debug?.upstream_nodes) {
        nodesToHighlight.push(...debug.upstream_nodes);
    }
    
    if (debug?.downstream_nodes) {
        nodesToHighlight.push(...debug.downstream_nodes);
    }
    
    // Add/highlight all nodes
    nodesToHighlight.forEach(node => {
        if (!node || !node.id) return;
        
        const existingNode = nodesDataset?.get(node.id);
        if (existingNode) {
            highlightNode(node.id, true);
        } else {
            addNodeToGraph(node, true);
        }
    });
    
    // Also highlight edges between these nodes
    const highlightedIds = new Set(nodesToHighlight.map(n => n?.id).filter(Boolean));
    
    edgesDataset?.forEach(edge => {
        const fromInSet = highlightedIds.has(edge.from);
        const toInSet = highlightedIds.has(edge.to);
        
        if (fromInSet && toInSet) {
            edgesDataset.update({
                id: edge.id,
                color: { color: HIGHLIGHT_COLOR, opacity: 1 },
                width: 3
            });
            highlightedEdges.add(edge.id);
        }
    });
    
    // If we have paths from sources, highlight those nodes too
    if (result.sources) {
        const pathSource = result.sources.find(s => s.type === 'path');
        if (pathSource && pathSource.value) {
            const pathLabels = pathSource.value.split(' → ');
            
            pathLabels.forEach(label => {
                const nodes = nodesDataset?.get({
                    filter: (node) => node.label?.toLowerCase() === label.toLowerCase()
                }) || [];
                
                nodes.forEach(node => highlightNode(node.id, true));
            });
        }
    }
    
    // Fit view to show all highlighted nodes
    if (highlightedNodes.size > 0 && network) {
        setTimeout(() => {
            network.fit({
                nodes: Array.from(highlightedNodes),
                animation: {
                    duration: 500,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 100);
    }
    
    console.log(`🔦 Highlighted ${highlightedNodes.size} nodes and ${highlightedEdges.size} edges`);
}

function addNodeToGraph(nodeData, highlight = false) {
    if (!nodesDataset || nodesDataset.get(nodeData.id)) return;

    const newNode = {
        id: nodeData.id,
        label: truncateLabel(nodeData.label || nodeData.id),
        // title removed - we use custom popup instead of vis.js tooltip
        color: highlight ? HIGHLIGHT_COLOR : getNodeColor(nodeData),
        shape: NODE_SHAPES[nodeData.type] || 'dot',
        size: highlight ? 25 : getNodeSize(nodeData),
        font: {
            color: highlight ? '#000' : '#e4e6eb',
            size: highlight ? 14 : 10
        },
        tier: nodeData.tier,
        type: nodeData.type,
        originalColor: getNodeColor(nodeData),
        data: nodeData
    };
    
    nodesDataset.add(newNode);
    
    if (highlight) {
        highlightedNodes.add(nodeData.id);
    }
}

function highlightNode(nodeId, isHighlighted) {
    if (isHighlighted) {
        highlightedNodes.add(nodeId);
        nodesDataset.update({
            id: nodeId,
            color: HIGHLIGHT_COLOR,
            size: 25,
            font: { size: 14, color: '#000' }
        });
    } else {
        highlightedNodes.delete(nodeId);
        const node = nodesDataset.get(nodeId);
        if (node) {
            nodesDataset.update({
                id: nodeId,
                color: node.originalColor,
                size: getNodeSize(node.data || {}),
                font: { size: 10, color: '#e4e6eb' }
            });
        }
    }
}

function clearHighlights() {
    // Reset highlighted nodes
    highlightedNodes.forEach(nodeId => highlightNode(nodeId, false));
    highlightedNodes.clear();
    
    // Reset highlighted edges
    highlightedEdges.forEach(edgeId => {
        edgesDataset?.update({
            id: edgeId,
            color: { color: '#30363d', opacity: 0.6 },
            width: 1
        });
    });
    highlightedEdges.clear();
}

// ===========================================
// Search & Navigation
// ===========================================

async function searchNodes(event) {
    const query = event.target.value.trim().toLowerCase();
    const resultsContainer = document.getElementById('search-results');
    
    if (query.length < 2) {
        resultsContainer.innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/graph/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, limit: 10 })
        });
        
        if (!response.ok) throw new Error('Search failed');
        
        const data = await response.json();
        displaySearchResults(data.results || []);
        
    } catch (error) {
        console.error('Search error:', error);
        // Fallback: search local nodes
        const localResults = nodesDataset?.get({
            filter: (node) => {
                return node.label?.toLowerCase().includes(query) ||
                       node.id?.toLowerCase().includes(query);
            }
        }) || [];
        
        displaySearchResults(localResults.slice(0, 10).map(n => n.data || n));
    }
}

function displaySearchResults(results) {
    const container = document.getElementById('search-results');
    container.innerHTML = '';
    
    results.forEach(node => {
        const div = document.createElement('div');
        div.className = 'search-result-item';
        div.innerHTML = `
            <span class="result-label">${node.label || node.id}</span>
            <span class="result-type">${node.type}</span>
        `;
        div.addEventListener('click', () => {
            searchAndFocusNode(node.id);
            container.innerHTML = '';
            document.getElementById('node-search').value = '';
        });
        container.appendChild(div);
    });
}

function searchAndFocusNode(identifier) {
    // Try to find node by ID or label
    const node = nodesDataset?.get(identifier) ||
                 nodesDataset?.get({
                     filter: (n) => n.label?.toLowerCase() === identifier.toLowerCase()
                 })?.[0];
    
    if (node) {
        focusOnNode(node.id);
        selectNode(node.id);
    } else {
        showToast(`Node "${identifier}" not found in current view`, 'warning');
    }
}

function focusOnNode(nodeId) {
    if (network) {
        network.focus(nodeId, {
            scale: 1.5,
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuad'
            }
        });
        network.selectNodes([nodeId]);
    }
}

// ===========================================
// Graph Controls
// ===========================================

function filterGraph() {
    const enabledTiers = new Set();
    
    document.querySelectorAll('.tier-checkbox input:checked').forEach(checkbox => {
        enabledTiers.add(parseInt(checkbox.value));
    });
    
    nodesDataset?.forEach(node => {
        const tier = node.tier !== undefined ? node.tier : -1;
        const visible = enabledTiers.has(tier);
        
        nodesDataset.update({
            id: node.id,
            hidden: !visible
        });
    });
}

function resetView() {
    if (network) {
        network.fit({
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
    clearHighlights();
    clearNodeSelection();
}

function fitGraph() {
    if (network) {
        network.fit({
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

async function showTraversal(direction) {
    if (!selectedNodeId) {
        showToast('Please select a node first', 'warning');
        return;
    }
    
    const maxDepth = parseInt(document.getElementById('max-depth').value) || 3;
    const result = await fetchTraversal(selectedNodeId, direction, maxDepth);
    
    if (result && result.nodes) {
        clearHighlights();
        
        // Highlight the selected node
        highlightNode(selectedNodeId, true);
        
        // Highlight/add connected nodes
        result.nodes.forEach(node => {
            const existingNode = nodesDataset?.get(node.id);
            if (existingNode) {
                highlightNode(node.id, true);
            } else {
                addNodeToGraph(node, true);
            }
        });
        
        // Add/highlight edges
        if (result.edges) {
            result.edges.forEach((edge, idx) => {
                const edgeId = `dynamic-edge-${edge.source}-${edge.target}`;
                const existingEdge = edgesDataset?.get(edgeId);
                
                if (!existingEdge) {
                    // Add new edge
                    edgesDataset?.add({
                        id: edgeId,
                        from: edge.source,
                        to: edge.target,
                        arrows: 'to',
                        color: { color: HIGHLIGHT_COLOR, opacity: 1 },
                        width: 3,
                        type: edge.type
                    });
                } else {
                    // Highlight existing edge
                    edgesDataset?.update({
                        id: edgeId,
                        color: { color: HIGHLIGHT_COLOR, opacity: 1 },
                        width: 3
                    });
                }
                highlightedEdges.add(edgeId);
            });
        }
        
        // Fit view to highlighted nodes
        if (highlightedNodes.size > 0) {
            setTimeout(() => {
                network?.fit({
                    nodes: Array.from(highlightedNodes),
                    animation: { duration: 500, easingFunction: 'easeInOutQuad' }
                });
            }, 100);
        }
        
        showToast(`Found ${result.count} ${direction} nodes`, 'success');
    }
}

// ===========================================
// Tabs
// ===========================================

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
}

// ===========================================
// Utilities
// ===========================================

function showNodePopup(event, node) {
    const popup = document.getElementById('network-popup');
    if (!popup) return;

    const tierName = node.tier_name || '';
    const definition = node.definition || node.payload || '';
    const tierColor = TIER_COLORS[node.tier] || TIER_COLORS['-1'];

    popup.innerHTML = `
        <div class="popup-header">
            <div class="popup-title">${node.label || node.id}</div>
            <div class="popup-badges">
                <span class="popup-badge" style="background: ${tierColor}20; color: ${tierColor}; border: 1px solid ${tierColor}40;">
                    ${node.type}
                </span>
                ${node.tier >= 0 ? `<span class="popup-badge" style="background: ${tierColor}20; color: ${tierColor}; border: 1px solid ${tierColor}40;">
                    Tier ${node.tier}${tierName ? ' - ' + tierName : ''}
                </span>` : ''}
            </div>
        </div>
        ${node.section ? `<div class="popup-section">📁 ${node.section}</div>` : ''}
        ${definition ? `<div class="popup-definition">${definition.length > 250 ? definition.substring(0, 250) + '...' : definition}</div>` : ''}
        <div class="popup-hint">Click to select • Double-click to focus</div>
    `;

    // Position popup near cursor
    const x = event.pageX || event.clientX;
    const y = event.pageY || event.clientY;

    popup.style.left = (x + 15) + 'px';
    popup.style.top = (y + 15) + 'px';
    popup.style.display = 'block';
    popup.style.opacity = '1';
}

function hideNodePopup() {
    const popup = document.getElementById('network-popup');
    if (popup) {
        popup.style.opacity = '0';
        setTimeout(() => {
            popup.style.display = 'none';
        }, 200);
    }
}

function createThinkingStep(stepNumber, title, description, details, status = 'success') {
    const stepDiv = document.createElement('div');
    stepDiv.className = 'thinking-step';

    const statusIcon = status === 'success' ? '✓' : status === 'processing' ? '⏳' : '•';
    const statusClass = status === 'success' ? 'success' : status === 'processing' ? 'processing' : 'neutral';

    stepDiv.innerHTML = `
        <div class="step-header">
            <div class="step-number ${statusClass}">${stepNumber}</div>
            <div class="step-info">
                <div class="step-title">${title}</div>
                <div class="step-description">${description}</div>
            </div>
            <div class="step-status ${statusClass}">${statusIcon}</div>
        </div>
        <div class="step-details">${details}</div>
    `;

    return stepDiv;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ'}</span>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===========================================
// Export for debugging
// ===========================================

window.GraphRAG = {
    get network() { return network; },
    get nodesDataset() { return nodesDataset; },
    get edgesDataset() { return edgesDataset; },
    get allNodes() { return allNodes; },
    get allEdges() { return allEdges; },
    get highlightedNodes() { return highlightedNodes; },
    API_BASE_URL,
    // Helper functions
    focusOnNode,
    highlightNode,
    clearHighlights,
    searchAndFocusNode
};
