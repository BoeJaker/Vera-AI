/**
 * GraphStyle - Visual styling and label management
 */

(function() {
    'use strict';
    
    window.GraphStyle = {
        networkInstance: null,
        dataModule: null,
        initialized: false,
        
        currentNodeStyle: 'dot',
        nodeLabelProperty: 'display_name',
        edgeLabelProperty: 'label',
        
        async init(networkInstance, dataModule) {
            console.log('GraphStyle: Initializing...');
            this.networkInstance = networkInstance;
            this.dataModule = dataModule;
            this._setupLabelControls();
            this.initialized = true;
        },
        
        _setupLabelControls() {
            // Populate dropdowns with available properties
            this.populateLabelOptions();
            
            // Set up change listeners
            const nodeSelect = document.getElementById('node-label-property');
            const edgeSelect = document.getElementById('edge-label-property');
            const styleSelect = document.getElementById('nodeStyle');
            
            if (nodeSelect) {
                nodeSelect.addEventListener('change', () => this.updateNodeLabels());
            }
            
            if (edgeSelect) {
                edgeSelect.addEventListener('change', () => this.updateEdgeLabels());
            }
            
            if (styleSelect) {
                styleSelect.addEventListener('change', () => this.updateNodeStyle());
            }
        },
        
        populateLabelOptions() {
            const nodeProps = new Set(['display_name', 'id', 'label']);
            const edgeProps = new Set(['label', 'type', 'title', 'id']);
            
            // Collect properties from nodes
            Object.values(this.dataModule.nodesData).forEach(node => {
                if (node.properties) {
                    Object.keys(node.properties).forEach(key => nodeProps.add(key));
                }
            });
            
            // Collect properties from edges
            const edges = this.networkInstance.body.data.edges.get();
            edges.forEach(edge => {
                Object.keys(edge).forEach(key => {
                    if (key !== 'from' && key !== 'to' && key !== 'arrows') {
                        edgeProps.add(key);
                    }
                });
            });
            
            // Update dropdowns
            this._updateSelect('node-label-property', nodeProps, this.nodeLabelProperty);
            this._updateSelect('edge-label-property', edgeProps, this.edgeLabelProperty);
            
            console.log(`GraphStyle: Label options populated (${nodeProps.size} node, ${edgeProps.size} edge)`);
        },
        
        _updateSelect(selectId, options, currentValue) {
            const select = document.getElementById(selectId);
            if (!select) return;
            
            select.innerHTML = '';
            options.forEach(prop => {
                const option = document.createElement('option');
                option.value = prop;
                option.textContent = prop.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                select.appendChild(option);
            });
            
            if (currentValue && options.has(currentValue)) {
                select.value = currentValue;
            }
        },
        
        updateNodeLabels() {
            const property = document.getElementById('node-label-property')?.value;
            if (!property) return;
            
            this.nodeLabelProperty = property;
            console.log('GraphStyle: Updating node labels to:', property);
            
            try {
                const nodeUpdates = [];
                
                this.networkInstance.body.data.nodes.forEach(node => {
                    const nodeData = this.dataModule.getNode(node.id);
                    let newLabel = node.id;
                    
                    if (nodeData) {
                        if (property === 'display_name') {
                            newLabel = nodeData.display_name || node.id;
                        } else if (property === 'id') {
                            newLabel = node.id;
                        } else if (property === 'label' && nodeData.labels?.[0]) {
                            newLabel = nodeData.labels[0];
                        } else if (nodeData.properties?.[property]) {
                            newLabel = String(nodeData.properties[property]);
                            if (newLabel.length > 50) {
                                newLabel = newLabel.substring(0, 50) + '...';
                            }
                        }
                    }
                    
                    nodeUpdates.push({ id: node.id, label: newLabel });
                });
                
                this.networkInstance.body.data.nodes.update(nodeUpdates);
                console.log(`GraphStyle: Updated ${nodeUpdates.length} node labels`);
                
            } catch (error) {
                console.error('GraphStyle: Error updating node labels:', error);
            }
        },
        
        updateEdgeLabels() {
            const property = document.getElementById('edge-label-property')?.value;
            if (!property) return;
            
            this.edgeLabelProperty = property;
            console.log('GraphStyle: Updating edge labels to:', property);
            
            try {
                const edgeUpdates = [];
                
                this.networkInstance.body.data.edges.forEach(edge => {
                    let newLabel = '';
                    
                    if (edge[property]) {
                        newLabel = String(edge[property]);
                        if (newLabel.length > 30) {
                            newLabel = newLabel.substring(0, 30) + '...';
                        }
                    }
                    
                    edgeUpdates.push({ id: edge.id, label: newLabel });
                });
                
                this.networkInstance.body.data.edges.update(edgeUpdates);
                console.log(`GraphStyle: Updated ${edgeUpdates.length} edge labels`);
                
            } catch (error) {
                console.error('GraphStyle: Error updating edge labels:', error);
            }
        },
        
        updateNodeStyle() {
            const style = document.getElementById('nodeStyle')?.value || 'dot';
            this.currentNodeStyle = style;
            
            console.log('GraphStyle: Updating node style to:', style);
            
            try {
                const nodeUpdates = [];
                
                this.networkInstance.body.data.nodes.forEach(node => {
                    const nodeData = this.dataModule.getNode(node.id);
                    const nodeColor = node.color || '#3b82f6';
                    
                    const updateData = { id: node.id };
                    
                    if (style === 'card') {
                        updateData.shape = 'box';
                        updateData.label = this._createCardLabel(nodeData, node);
                        updateData.font = {
                            multi: true,
                            color: '#000000',
                            size: 12,
                            face: 'arial',
                            align: 'left',
                            bold: { color: '#000000', size: 14 }
                        };
                        updateData.widthConstraint = { minimum: 180, maximum: 280 };
                        updateData.heightConstraint = { minimum: 60 };
                        updateData.margin = 12;
                        updateData.shapeProperties = { borderRadius: 6 };
                        
                        if (typeof nodeColor === 'string') {
                            updateData.color = {
                                background: nodeColor,
                                border: this._adjustBrightness(nodeColor, 20),
                                highlight: {
                                    background: this._adjustBrightness(nodeColor, -10),
                                    border: this._adjustBrightness(nodeColor, 40)
                                }
                            };
                        }
                    } else if (style === 'box') {
                        updateData.shape = 'box';
                        updateData.font = { color: '#ffffff', size: 14, face: 'arial' };
                        updateData.widthConstraint = { minimum: 80, maximum: 200 };
                        updateData.heightConstraint = { minimum: 40 };
                        if (nodeColor) updateData.color = nodeColor;
                    } else {
                        updateData.shape = style;
                        updateData.font = { color: '#ffffff', size: 14 };
                        if (nodeColor) updateData.color = nodeColor;
                    }
                    
                    nodeUpdates.push(updateData);
                });
                
                this.networkInstance.body.data.nodes.update(nodeUpdates);
                this.networkInstance.redraw();
                
            } catch (error) {
                console.error('GraphStyle: Error updating node style:', error);
            }
        },
        
        _createCardLabel(nodeData, node) {
            if (!nodeData) return node.label || node.id;
            
            const title = nodeData.display_name || node.id;
            const labels = nodeData.labels || [];
            const props = nodeData.properties || {};
            
            let bodyText = props.text || props.body || props.summary || props.description || '';
            if (bodyText.length > 100) {
                bodyText = bodyText.substring(0, 100) + '...';
            }
            
            let label = title;
            
            if (labels.length > 0) {
                label += '\n[' + labels.slice(0, 3).join(', ') + ']';
            }
            
            if (bodyText) {
                label += '\n' + bodyText;
            }
            
            return label;
        },
        
        _adjustBrightness(color, percent) {
            if (!color || !color.startsWith('#')) return color;
            
            const num = parseInt(color.replace('#', ''), 16);
            const amt = Math.round(2.55 * percent);
            const R = Math.max(0, Math.min(255, (num >> 16) + amt));
            const G = Math.max(0, Math.min(255, ((num >> 8) & 0x00FF) + amt));
            const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
            
            return '#' + ((R << 16) + (G << 8) + B).toString(16).padStart(6, '0');
        },
        
        updateSettings() {
            const baseSize = parseInt(document.getElementById('nodeSize')?.value || 25);
            const edgeWidth = parseInt(document.getElementById('edgeWidth')?.value || 2);
            const physicsStrength = parseFloat(document.getElementById('physics')?.value || 0.01);
            
            document.getElementById('nodeSizeVal').innerText = baseSize;
            document.getElementById('edgeWidthVal').innerText = edgeWidth;
            document.getElementById('physicsVal').innerText = physicsStrength.toFixed(3);
            
            // Update nodes
            const nodeUpdates = this.networkInstance.body.data.nodes.map(node => ({
                id: node.id,
                size: baseSize
            }));
            this.networkInstance.body.data.nodes.update(nodeUpdates);
            
            // Update edges
            const edgeUpdates = this.networkInstance.body.data.edges.map(edge => ({
                id: edge.id,
                width: edgeWidth
            }));
            this.networkInstance.body.data.edges.update(edgeUpdates);
            
            // Update physics
            this.networkInstance.setOptions({
                physics: {
                    barnesHut: { springConstant: physicsStrength }
                }
            });
        }
    };
})();