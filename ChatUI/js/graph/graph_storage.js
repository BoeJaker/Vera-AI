(() => {
    /**
     * Graph Storage Menu
     * Creates a floating menu to manage saved graphs
     */
    window.showGraphStorageMenu = function(veraChatInstance) {
        // Remove existing menu if any
        const existingMenu = document.getElementById('graphStorageMenu');
        if (existingMenu) existingMenu.remove();

        // Create menu container
        const menu = document.createElement('div');
        menu.id = 'graphStorageMenu';
        Object.assign(menu.style, {
            position: 'fixed',
            top: '50px',
            right: '50px',
            width: '280px',
            maxHeight: '400px',
            overflowY: 'auto',
            backgroundColor: '#1e293b',
            color: '#ffffff',
            border: '2px solid #3b82f6',
            borderRadius: '12px',
            padding: '10px',
            zIndex: 9999,
            boxShadow: '0 8px 16px rgba(0,0,0,0.3)',
            fontFamily: 'sans-serif'
        });

        // Title
        const title = document.createElement('h3');
        title.textContent = 'Graph Storage';
        Object.assign(title.style, { margin: '0 0 10px 0', fontSize: '18px', textAlign: 'center' });
        menu.appendChild(title);

        // List of saved graphs
        const list = document.createElement('ul');
        Object.assign(list.style, { listStyle: 'none', padding: '0', margin: '0 0 10px 0' });

        // Find saved graphs in localStorage
        const keys = Object.keys(localStorage).filter(k => k.startsWith('graph_'));
        if (keys.length === 0) {
            const emptyMsg = document.createElement('p');
            emptyMsg.textContent = 'No saved graphs';
            emptyMsg.style.textAlign = 'center';
            list.appendChild(emptyMsg);
        } else {
            keys.forEach(k => {
                const li = document.createElement('li');
                li.style.display = 'flex';
                li.style.justifyContent = 'space-between';
                li.style.marginBottom = '6px';

                const nameSpan = document.createElement('span');
                nameSpan.textContent = k.replace('graph_', '');
                li.appendChild(nameSpan);

                const loadBtn = document.createElement('button');
                loadBtn.textContent = 'Load';
                Object.assign(loadBtn.style, { marginRight: '4px' });
                loadBtn.onclick = () => {
                    window.graphStorageUtils.loadFromLocal(veraChatInstance, k.replace('graph_', ''));
                };
                li.appendChild(loadBtn);

                const delBtn = document.createElement('button');
                delBtn.textContent = 'Delete';
                delBtn.onclick = () => {
                    localStorage.removeItem(k);
                    li.remove();
                };
                li.appendChild(delBtn);

                list.appendChild(li);
            });
        }

        menu.appendChild(list);

        // Input + save button
        const inputWrapper = document.createElement('div');
        Object.assign(inputWrapper.style, { display: 'flex', marginTop: '10px' });

        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Graph name...';
        Object.assign(input.style, { flex: '1', padding: '4px', borderRadius: '4px', border: '1px solid #3b82f6', marginRight: '4px' });
        inputWrapper.appendChild(input);

        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Save';
        saveBtn.onclick = () => {
            const name = input.value.trim();
            if (!name) return alert('Please enter a name');
            window.graphStorageUtils.saveToLocal(veraChatInstance, name);

            // Add new entry to menu
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.style.marginBottom = '6px';

            const nameSpan = document.createElement('span');
            nameSpan.textContent = name;
            li.appendChild(nameSpan);

            const loadBtn = document.createElement('button');
            loadBtn.textContent = 'Load';
            loadBtn.onclick = () => window.graphStorageUtils.loadFromLocal(veraChatInstance, name);
            li.appendChild(loadBtn);

            const delBtn = document.createElement('button');
            delBtn.textContent = 'Delete';
            delBtn.onclick = () => { localStorage.removeItem('graph_' + name); li.remove(); };
            li.appendChild(delBtn);

            list.appendChild(li);
            input.value = '';
        };
        inputWrapper.appendChild(saveBtn);

        menu.appendChild(inputWrapper);

        // Close button
        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        Object.assign(closeBtn.style, {
            display: 'block',
            width: '100%',
            marginTop: '10px',
            padding: '6px 0',
            borderRadius: '6px',
            backgroundColor: '#3b82f6',
            border: 'none',
            color: '#fff',
            cursor: 'pointer'
        });
        closeBtn.onclick = () => menu.remove();
        menu.appendChild(closeBtn);

        document.body.appendChild(menu);
    };
})();
