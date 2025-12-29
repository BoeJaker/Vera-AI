(() => {
    /**
     * Save/Load module for VeraChat graphs
     * Integrates with loader and supports animation on reload
     */
    window.graphStorageUtils = {
        /**
         * Save current graph to localStorage
         * @param {VeraChat} veraChatInstance
         * @param {string} name - optional name key for storage
         */
        saveToLocal: function(veraChatInstance, name = 'defaultGraph') {
            if (!veraChatInstance.networkData) return;
            const json = JSON.stringify(veraChatInstance.networkData);
            localStorage.setItem(`graph_${name}`, json);
            console.log(`Graph saved as '${name}' in localStorage`);
        },

        /**
         * Load graph from localStorage
         * @param {VeraChat} veraChatInstance
         * @param {string} name - storage key
         */
        loadFromLocal: function(veraChatInstance, name = 'defaultGraph') {
            const json = localStorage.getItem(`graph_${name}`);
            if (!json) return console.warn(`No saved graph found for '${name}'`);
            const data = JSON.parse(json);
            this.loadGraphData(veraChatInstance, data);
        },

        /**
         * Download current graph as JSON file
         */
        downloadGraph: function(veraChatInstance, filename = 'graph.json') {
            if (!veraChatInstance.networkData) return;
            const dataStr = JSON.stringify(veraChatInstance.networkData, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            console.log(`Graph downloaded as '${filename}'`);
        },

        /**
         * Load graph from JSON object
         * Replaces current graph and animates nodes/edges
         */
        loadGraphData: function(veraChatInstance, data) {
            if (!data || !data.nodes || !data.edges) return;

            // Show loader during reload
            graphLoaderUtils.setLoading(true);
            graphLoaderUtils.show('Loading saved graph');

            // Clear current graph
            veraChatInstance.clearGraph();

            // Animate adding nodes/edges
            setTimeout(() => {
                veraChatInstance.addNodesToGraph(data.nodes, data.edges);
                
                // Update internal data array
                veraChatInstance.networkData.nodes = [...data.nodes];
                veraChatInstance.networkData.edges = [...data.edges];

                // Update counters
                document.getElementById('nodeCount').textContent = data.nodes.length;
                document.getElementById('edgeCount').textContent = data.edges.length;

                // Hide loader after animation
                setTimeout(() => {
                    graphLoaderUtils.setLoading(false);
                    graphLoaderUtils.hide(true);
                    console.log('Saved graph loaded successfully');
                }, 1500); // matches addNodesToGraph animation delay

            }, 100); // small delay for loader visibility
        },

        /**
         * Load from JSON file via <input type="file">
         */
        loadFromFile: function(veraChatInstance, file) {
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                const data = JSON.parse(e.target.result);
                this.loadGraphData(veraChatInstance, data);
            };
            reader.readAsText(file);
        }
    };

    /**
     * Optional helper to attach file input listener
     */
    window.setupGraphFileInput = function(inputId, veraChatInstance) {
        const input = document.getElementById(inputId);
        if (!input) return console.warn('File input not found:', inputId);

        input.addEventListener('change', (evt) => {
            const file = evt.target.files[0];
            if (!file) return;
            window.graphStorageUtils.loadFromFile(veraChatInstance, file);
        });
    };
})();
