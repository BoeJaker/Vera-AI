/**
 * Calendar Module for Vera AI - IMPROVED VERSION
 * - Collapsible sidebars
 * - Responsive horizontal scaling
 * - Minimal emoji usage
 * - Fixed duplicate event bug
 * - Scheduling agent chat interface
 */

class CalendarManager {
    constructor() {
        this.calendar = null;
        this.ws = null;
        this.sources = [];
        this.currentView = 'dayGridMonth';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.initialized = false;
        
        // Sidebar collapse state
        this.leftSidebarCollapsed = false;
        this.rightSidebarCollapsed = false;
        
        // API Configuration
        this.apiBase = this.getApiBase();
        console.log('[Calendar] CalendarManager created');
    }
    
    getApiBase() {
        if (window.location.protocol !== 'file:') {
            const protocol = window.location.protocol;
            const host = window.location.hostname;
            const port = window.location.port || '8888';
            return `${protocol}//${host}:${port}`;
        } else {
            return 'http://llm.int:8888';
        }
    }
    
    async init() {
        if (this.initialized) {
            console.log('[Calendar] Already initialized');
            return;
        }
        
        console.log('[Calendar] Initializing...');
        
        const container = document.getElementById('calendar-container');
        if (!container) {
            console.error('[Calendar] calendar-container not found');
            this.showNotification('Calendar container not found', 'error');
            return;
        }
        
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('[Calendar] calendar element not found');
            this.showNotification('Calendar element not found', 'error');
            return;
        }
        
        try {
            await this.loadFullCalendar();
            await this.loadSources();
            this.initCalendar();
            this.setupWebSocket();
            await this.loadEvents();
            this.setupEventHandlers();
            await this.loadCronJobs();
            this.setupSidebarToggles();
            
            this.initialized = true;
            console.log('[Calendar] Initialization complete');
            this.showNotification('Calendar loaded', 'success');
            
        } catch (error) {
            console.error('[Calendar] Initialization failed:', error);
            this.showNotification('Initialization failed', 'error');
        }
    }
    
    destroy() {
        if (this.calendar) {
            this.calendar.destroy();
            this.calendar = null;
        }
        
        if (this.ws) {
            this.stopHeartbeat();
            this.ws.close();
            this.ws = null;
        }
        
        this.initialized = false;
    }
    
    async loadFullCalendar() {
        if (typeof FullCalendar !== 'undefined') {
            return;
        }
        
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    async loadSources() {
        try {
            const url = `${this.apiBase}/api/calendar/sources`;
            const response = await fetch(url);
            const data = await response.json();
            this.sources = data.sources;
            this.renderSourceFilters();
        } catch (error) {
            this.sources = [
                {"id": "google", "name": "Google Calendar", "color": "#4285f4", "enabled": true},
                {"id": "local", "name": "Local Calendar", "color": "#34a853", "enabled": true},
                {"id": "apscheduler", "name": "Scheduled Jobs", "color": "#fbbc04", "enabled": true}
            ];
            this.renderSourceFilters();
        }
    }
    
    initCalendar() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) return;
        
        this.calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: this.currentView,
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
            },
            editable: true,
            selectable: true,
            selectMirror: true,
            dayMaxEvents: true,
            weekends: true,
            height: 'auto',
            
            select: (info) => this.handleDateSelect(info),
            eventClick: (info) => this.handleEventClick(info),
            eventDrop: (info) => this.handleEventDrop(info),
            eventResize: (info) => this.handleEventResize(info),
            eventContent: (arg) => this.renderEventContent(arg),
            
            datesSet: (info) => {
                this.currentView = info.view.type;
            },
            
            businessHours: {
                daysOfWeek: [1, 2, 3, 4, 5],
                startTime: '09:00',
                endTime: '17:00'
            }
        });
        
        this.calendar.render();
    }
    
    async loadEvents() {
        try {
            const url = `${this.apiBase}/api/calendar/events?days_ahead=30`;
            console.log('[Calendar] Fetching events from:', url);
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const events = await response.json();
            console.log('[Calendar] Received', events.length, 'events from API');
            
            if (this.calendar) {
                const oldEventCount = this.calendar.getEvents().length;
                console.log('[Calendar] Removing', oldEventCount, 'existing events');
                this.calendar.removeAllEvents();
                
                events.forEach((event, index) => {
                    const calendarEvent = {
                        id: `${event.source}_${event.id}`,
                        title: event.title,
                        start: event.start,
                        end: event.end || event.start,
                        backgroundColor: event.color || this.getSourceColor(event.source),
                        borderColor: event.color || this.getSourceColor(event.source),
                        extendedProps: {
                            source: event.source,
                            originalId: event.id,
                            description: event.description,
                            recurrence: event.recurrence
                        },
                        allDay: event.all_day || false
                    };
                    
                    console.log(`[Calendar] Adding event ${index + 1}:`, {
                        id: calendarEvent.id,
                        title: calendarEvent.title,
                        start: calendarEvent.start,
                        end: calendarEvent.end,
                        startParsed: new Date(calendarEvent.start),
                        endParsed: new Date(calendarEvent.end)
                    });
                    
                    this.calendar.addEvent(calendarEvent);
                });
                
                // Verify events were added
                const newEventCount = this.calendar.getEvents().length;
                console.log('[Calendar] Now have', newEventCount, 'events in calendar');
                
                // Get current view date range
                const view = this.calendar.view;
                console.log('[Calendar] Current view:', {
                    type: view.type,
                    start: view.currentStart,
                    end: view.currentEnd,
                    title: view.title
                });
                
                // Check if events are in view
                events.forEach(event => {
                    const eventStart = new Date(event.start);
                    const inView = eventStart >= view.currentStart && eventStart <= view.currentEnd;
                    if (!inView) {
                        console.warn('[Calendar] Event NOT in current view:', {
                            title: event.title,
                            start: event.start,
                            startDate: eventStart,
                            viewStart: view.currentStart,
                            viewEnd: view.currentEnd
                        });
                    }
                });
            }
            
            this.updateStats(events);
        } catch (error) {
            console.error('[Calendar] Error loading events:', error);
        }
    }
    
    setupWebSocket() {
        const protocol = this.apiBase.startsWith('https') ? 'wss:' : 'ws:';
        const host = this.apiBase.replace(/^https?:\/\//, '');
        const wsUrl = `${protocol}//${host}/api/calendar/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.updateConnectionStatus('connected');
            this.ws.send(JSON.stringify({ type: 'subscribe' }));
            this.startHeartbeat();
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            } catch (error) {
                console.error('[Calendar WS] Parse error:', error);
            }
        };
        
        this.ws.onerror = () => {
            this.updateConnectionStatus('error');
        };
        
        this.ws.onclose = () => {
            this.updateConnectionStatus('disconnected');
            this.stopHeartbeat();
            if (this.initialized) {
                this.attemptReconnect();
            }
        };
    }
    
    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'subscribed':
                break;
                
            case 'events_update':
                this.loadEvents();
                break;
                
            case 'event_created':
                // Don't reload here - createEvent() already does it
                // This prevents double notifications
                console.log('[Calendar WS] Event created (ignoring - already handled)');
                break;
                
            case 'event_deleted':
                const deletedId = `${message.data.source}_${message.data.id}`;
                if (this.calendar) {
                    const event = this.calendar.getEventById(deletedId);
                    if (event) event.remove();
                }
                this.showNotification('Event deleted', 'info');
                break;
        }
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        
        setTimeout(() => {
            this.setupWebSocket();
        }, delay);
    }
    
    handleDateSelect(info) {
        this.showCreateEventModal(info.start, info.end, info.allDay);
        if (this.calendar) {
            this.calendar.unselect();
        }
    }
    
    handleEventClick(info) {
        this.showEventDetailsModal(info.event);
    }
    
    handleEventDrop(info) {
        this.showNotification(`Moved: ${info.event.title}`, 'info');
    }
    
    handleEventResize(info) {
        this.showNotification(`Resized: ${info.event.title}`, 'info');
    }
    
    renderEventContent(arg) {
        return {
            html: `
                <div class="fc-event-main-frame">
                    <div class="fc-event-time">${arg.timeText}</div>
                    <div class="fc-event-title">${arg.event.title}</div>
                </div>
            `
        };
    }
    
    showCreateEventModal(start, end, allDay = false) {
        const modal = document.getElementById('eventModal');
        if (!modal) return;
        
        const form = document.getElementById('eventForm');
        const titleInput = document.getElementById('eventTitle');
        const startInput = document.getElementById('eventStart');
        const endInput = document.getElementById('eventEnd');
        const sourceSelect = document.getElementById('eventSource');
        const descriptionInput = document.getElementById('eventDescription');
        
        form.reset();
        
        // Format dates for datetime-local input (local time, no timezone conversion)
        startInput.value = this.formatDatetimeLocal(start);
        endInput.value = this.formatDatetimeLocal(end);
        
        console.log('[Calendar] Modal opened with dates:', {
            start: start,
            end: end,
            startInput: startInput.value,
            endInput: endInput.value
        });
        
        sourceSelect.innerHTML = this.sources
            .filter(s => s.enabled && s.id !== 'apscheduler')
            .map(s => `<option value="${s.id}">${s.name}</option>`)
            .join('');
        
        modal.style.display = 'flex';
        titleInput.focus();
        
        form.onsubmit = async (e) => {
            e.preventDefault();
            
            // Get values from inputs (these are in local time)
            const startLocal = startInput.value;
            const endLocal = endInput.value;
            
            // Create Date objects (these will be in local timezone)
            const startDate = new Date(startLocal);
            const endDate = new Date(endLocal);
            
            console.log('[Calendar] Form submitted with:', {
                startLocal,
                endLocal,
                startDate: startDate.toString(),
                endDate: endDate.toString(),
                startISO: startDate.toISOString(),
                endISO: endDate.toISOString()
            });
            
            const eventData = {
                title: titleInput.value,
                start: startDate.toISOString(),  // Send UTC to backend
                end: endDate.toISOString(),
                source: sourceSelect.value,
                description: descriptionInput.value || null
            };
            
            await this.createEvent(eventData);
            modal.style.display = 'none';
        };
    }
    
    showEventDetailsModal(event) {
        const modal = document.getElementById('eventDetailsModal');
        if (!modal) return;
        
        const content = document.getElementById('eventDetailsContent');
        const props = event.extendedProps;
        const source = this.sources.find(s => s.id === props.source);
        
        content.innerHTML = `
            <div class="event-details">
                <h3>${event.title}</h3>
                <div class="event-info">
                    <div class="info-row">
                        <strong>Source:</strong>
                        <span class="source-badge" style="background-color: ${source?.color || '#999'}">
                            ${source?.name || props.source}
                        </span>
                    </div>
                    <div class="info-row">
                        <strong>Start:</strong>
                        <span>${this.formatDatetime(event.start)}</span>
                    </div>
                    <div class="info-row">
                        <strong>End:</strong>
                        <span>${event.end ? this.formatDatetime(event.end) : 'N/A'}</span>
                    </div>
                    ${props.description ? `
                        <div class="info-row">
                            <strong>Description:</strong>
                            <p>${props.description}</p>
                        </div>
                    ` : ''}
                </div>
                <div class="event-actions">
                    <button class="btn btn-danger" onclick="window.calendarManager.deleteEvent('${props.source}', '${props.originalId}')">
                        Delete
                    </button>
                    <button class="btn btn-secondary" onclick="document.getElementById('eventDetailsModal').style.display='none'">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        modal.style.display = 'flex';
    }
    
    async createEvent(eventData) {
        try {
            const url = `${this.apiBase}/api/calendar/events`;
            console.log('[Calendar] Creating event:', eventData);
            
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(eventData)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create event');
            }
            
            const newEvent = await response.json();
            console.log('[Calendar] Event created:', newEvent);
            
            // Reload events immediately to show the new event
            await this.loadEvents();
            
            // Check if event is in current view
            if (this.calendar) {
                const view = this.calendar.view;
                const eventStart = new Date(newEvent.start);
                const inView = eventStart >= view.currentStart && eventStart <= view.currentEnd;
                
                if (inView) {
                    this.showNotification('Event created', 'success');
                } else {
                    // Event is outside current view
                    const eventDate = eventStart.toLocaleDateString();
                    this.showNotification(`Event created on ${eventDate} (navigate to see it)`, 'success');
                    
                    // Optional: Navigate to the event
                    setTimeout(() => {
                        if (confirm(`Event created on ${eventDate}. Navigate to it?`)) {
                            this.calendar.gotoDate(eventStart);
                        }
                    }, 500);
                }
            } else {
                this.showNotification('Event created', 'success');
            }
            
        } catch (error) {
            console.error('[Calendar] Error creating event:', error);
            this.showNotification(`Failed: ${error.message}`, 'error');
        }
    }
    
    async deleteEvent(source, eventId) {
        if (!confirm('Delete this event?')) return;
        
        try {
            const url = `${this.apiBase}/api/calendar/events/${source}/${eventId}`;
            const response = await fetch(url, { method: 'DELETE' });
            
            if (!response.ok) {
                throw new Error('Delete failed');
            }
            
            const calendarEventId = `${source}_${eventId}`;
            if (this.calendar) {
                const event = this.calendar.getEventById(calendarEventId);
                if (event) event.remove();
            }
            
            document.getElementById('eventDetailsModal').style.display = 'none';
            this.showNotification('Event deleted', 'success');
            
        } catch (error) {
            this.showNotification('Failed to delete', 'error');
        }
    }
    
    async loadCronJobs() {
        try {
            const url = `${this.apiBase}/api/calendar/cron`;
            const response = await fetch(url);
            const jobs = await response.json();
            this.renderCronJobs(jobs);
        } catch (error) {
            this.renderCronJobs([]);
        }
    }
    
    renderCronJobs(jobs) {
        const container = document.getElementById('cronJobsList');
        if (!container) return;
        
        if (jobs.length === 0) {
            container.innerHTML = '<p class="text-muted">No scheduled jobs</p>';
            return;
        }
        
        container.innerHTML = jobs.map(job => `
            <div class="cron-job-item">
                <div class="cron-job-header">
                    <strong>${job.name}</strong>
                    <span class="badge badge-${job.enabled ? 'success' : 'secondary'}">
                        ${job.enabled ? 'Active' : 'Inactive'}
                    </span>
                </div>
                <div class="cron-job-details">
                    <small>${job.schedule}</small>
                    ${job.next_run ? `<small>Next: ${this.formatDatetime(new Date(job.next_run))}</small>` : ''}
                </div>
            </div>
        `).join('');
    }
    
    renderSourceFilters() {
        const container = document.getElementById('sourceFilters');
        if (!container) return;
        
        container.innerHTML = this.sources.map(source => `
            <label class="source-filter ${!source.enabled ? 'disabled' : ''}">
                <input type="checkbox" 
                       value="${source.id}" 
                       ${source.enabled ? 'checked' : ''}
                       ${!source.enabled ? 'disabled' : ''}
                       onchange="window.calendarManager.toggleSource('${source.id}', this.checked)">
                <span class="source-color" style="background-color: ${source.color}"></span>
                <span>${source.name}</span>
            </label>
        `).join('');
    }
    
    toggleSource(sourceId, enabled) {
        if (this.calendar) {
            this.calendar.getEvents().forEach(event => {
                if (event.extendedProps.source === sourceId) {
                    event.setProp('display', enabled ? 'auto' : 'none');
                }
            });
        }
    }
    
    setupSidebarToggles() {
        const leftToggle = document.getElementById('toggleLeftSidebar');
        const rightToggle = document.getElementById('toggleRightSidebar');
        
        if (leftToggle) leftToggle.onclick = () => this.toggleLeftSidebar();
        if (rightToggle) rightToggle.onclick = () => this.toggleRightSidebar();
    }
    
    toggleLeftSidebar() {
        this.leftSidebarCollapsed = !this.leftSidebarCollapsed;
        const sidebar = document.querySelector('.calendar-sidebar-left');
        const container = document.getElementById('calendar-container');
        
        if (sidebar && container) {
            if (this.leftSidebarCollapsed) {
                sidebar.classList.add('collapsed');
                container.style.gridTemplateColumns = '50px 1fr ' + (this.rightSidebarCollapsed ? '50px' : '280px');
            } else {
                sidebar.classList.remove('collapsed');
                container.style.gridTemplateColumns = '250px 1fr ' + (this.rightSidebarCollapsed ? '50px' : '280px');
            }
            
            if (this.calendar) {
                setTimeout(() => this.calendar.updateSize(), 300);
            }
        }
    }
    
    toggleRightSidebar() {
        this.rightSidebarCollapsed = !this.rightSidebarCollapsed;
        const sidebar = document.querySelector('.calendar-sidebar-right');
        const container = document.getElementById('calendar-container');
        
        if (sidebar && container) {
            if (this.rightSidebarCollapsed) {
                sidebar.classList.add('collapsed');
                container.style.gridTemplateColumns = (this.leftSidebarCollapsed ? '50px' : '250px') + ' 1fr 50px';
            } else {
                sidebar.classList.remove('collapsed');
                container.style.gridTemplateColumns = (this.leftSidebarCollapsed ? '50px' : '250px') + ' 1fr 280px';
            }
            
            if (this.calendar) {
                setTimeout(() => this.calendar.updateSize(), 300);
            }
        }
    }
    
    setupEventHandlers() {
        // Modal handlers
        document.querySelectorAll('.modal').forEach(modal => {
            const closeBtn = modal.querySelector('.close');
            if (closeBtn) {
                closeBtn.onclick = () => modal.style.display = 'none';
            }
        });
        
        window.onclick = (event) => {
            document.querySelectorAll('.modal').forEach(modal => {
                if (event.target === modal) modal.style.display = 'none';
            });
        };
        
        // Button handlers
        const refreshBtn = document.getElementById('refreshCalendar');
        if (refreshBtn) {
            refreshBtn.onclick = () => {
                this.loadEvents();
                this.loadCronJobs();
            };
        }
        
        const newEventBtn = document.getElementById('newEventBtn');
        if (newEventBtn) {
            newEventBtn.onclick = () => {
                const now = new Date();
                const later = new Date(now.getTime() + 3600000);
                this.showCreateEventModal(now, later);
            };
        }
        
        // Agent chat
        this.setupAgentChat();
    }
    
    setupAgentChat() {
        const chatForm = document.getElementById('agentChatForm');
        const chatInput = document.getElementById('agentChatInput');
        
        if (chatForm) {
            chatForm.onsubmit = async (e) => {
                e.preventDefault();
                if (chatInput && chatInput.value.trim()) {
                    await this.sendAgentMessage(chatInput.value);
                    chatInput.value = '';
                }
            };
        }
    }
    
    async sendAgentMessage(message) {
        try {
            this.addChatMessage('user', message);
            const thinkingId = this.addChatMessage('assistant', 'Thinking...');
            
            const url = `${this.apiBase}/api/calendar/agent/chat`;
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            
            const data = await response.json();
            
            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();
            
            this.addChatMessage('assistant', data.response);
            
            if (data.events_changed) {
                this.loadEvents();
            }
            
        } catch (error) {
            console.error('[Calendar] Agent error:', error);
            this.addChatMessage('assistant', 'Error: Could not reach agent');
        }
    }
    
    addChatMessage(role, content) {
        const chatMessages = document.getElementById('agentChatMessages');
        if (!chatMessages) return;
        
        const messageId = 'msg-' + Date.now();
        const messageEl = document.createElement('div');
        messageEl.id = messageId;
        messageEl.className = `chat-message chat-message-${role}`;
        messageEl.innerHTML = `<div class="chat-message-content">${content}</div>`;
        
        chatMessages.appendChild(messageEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageId;
    }
    
    updateConnectionStatus(status) {
        const indicator = document.getElementById('connectionStatus');
        if (!indicator) return;
        
        const config = {
            connected: { text: 'Connected', class: 'status-connected' },
            disconnected: { text: 'Disconnected', class: 'status-disconnected' },
            error: { text: 'Error', class: 'status-error' }
        };
        
        const c = config[status] || config.disconnected;
        indicator.className = `connection-status ${c.class}`;
        indicator.textContent = c.text;
    }
    
    updateStats(events) {
        const statsEl = document.getElementById('calendarStats');
        if (!statsEl) return;
        
        const bySource = {};
        this.sources.forEach(s => bySource[s.id] = 0);
        events.forEach(e => {
            if (bySource[e.source] !== undefined) bySource[e.source]++;
        });
        
        const statsHTML = this.sources
            .filter(s => s.enabled)
            .map(s => `<span class="stat-item"><span class="stat-color" style="background-color: ${s.color}"></span>${bySource[s.id] || 0}</span>`)
            .join('');
        
        statsEl.innerHTML = `Total: ${events.length} | ${statsHTML}`;
    }
    
    getSourceColor(source) {
        const sourceObj = this.sources.find(s => s.id === source);
        return sourceObj?.color || '#999';
    }
    
    formatDatetime(date) {
        if (!date) return 'N/A';
        const d = new Date(date);
        return d.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    formatDatetimeLocal(date) {
        const d = new Date(date);
        const offset = d.getTimezoneOffset();
        const localDate = new Date(d.getTime() - (offset * 60 * 1000));
        return localDate.toISOString().slice(0, 16);
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `calendar-notification notification-${type}`;
        notification.textContent = message;
        
        let container = document.getElementById('notificationContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notificationContainer';
            container.className = 'notification-container';
            document.body.appendChild(container);
        }
        container.appendChild(notification);
        
        setTimeout(() => notification.classList.add('show'), 10);
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

window.calendarManager = new CalendarManager();
console.log('[Calendar] Ready. Call window.calendarManager.init() when tab is active.');