const API_BASE = window.__HHN_API_BASE || 'http://localhost:8000/api';

let routeMap = null;
let currentRouteMarkers = [];
let currentRouteLayers = []; // Track all route-related layers (markers, polylines, arrows)
let currentRouteData = null; // Store current route data for timeline interactions
let deliveryInfoCard = null; // Store reference to delivery info card
let selectedDriverId = null; // Track selected driver for filtering routes
let allDrivers = []; // Store all drivers

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    try {
        setupTabs();
        setupKeyboardShortcuts();
        loadOrders();
        loadDrivers();
        loadRoutes();
        loadDepots();
        loadParkingLocations();
        // Don't initialize map immediately - wait for routes tab to be shown
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});

// Keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + N: New order
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
            if (activeTab === 'orders') {
                showAddOrderModal();
            } else if (activeTab === 'drivers') {
                showAddDriverModal();
            } else if (activeTab === 'routes') {
                showCreateRouteModal();
            }
        }

        // Escape: Close modal
        if (e.key === 'Escape') {
            closeModal();
        }

        // Number keys 1-4: Switch tabs
        if (e.key >= '1' && e.key <= '4' && !e.ctrlKey && !e.metaKey) {
            const tabs = ['orders', 'drivers', 'routes', 'locations'];
            const tabIndex = parseInt(e.key) - 1;
            if (tabIndex < tabs.length) {
                document.querySelector(`[data-tab="${tabs[tabIndex]}"]`)?.click();
            }
        }
    });
}

// Tab switching
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');

            // Show/hide route header controls
            const routeControls = document.getElementById('route-header-controls');
            if (routeControls) {
                if (tab === 'routes') {
                    routeControls.style.display = 'flex';
                } else {
                    routeControls.style.display = 'none';
                }
            }

            // Initialize map and route planning UI when routes tab is shown
            if (tab === 'routes') {
                setTimeout(() => {
                    if (!routeMap) {
                        initRouteMap();
                        console.log('Map initialized for routes tab');
                    } else {
                        routeMap.invalidateSize();
                        console.log('Map size invalidated');
                    }
                    // Initialize route planning UI
                    initRoutePlanningUI();
                    // Setup collapse toggle
                    setupRoutesPanelCollapse();
                }, 200); // Small delay to ensure container is visible
            }

            // Load summary data when summary tab is shown
            if (tab === 'summary') {
                loadSummary();
            }

            // Load archive data when archive tab is shown
            if (tab === 'archive') {
                loadArchive();
            }
        });
    });

    // Setup navigation collapse toggle
    setupNavCollapse();

    // Initialize route controls visibility on page load
    const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
    const routeControls = document.getElementById('route-header-controls');
    if (routeControls) {
        if (activeTab === 'routes') {
            routeControls.style.display = 'flex';
        } else {
            routeControls.style.display = 'none';
        }
    }
}

// Navigation collapse functionality
function setupNavCollapse() {
    try {
        const collapseBtn = document.getElementById('nav-collapse-btn');
        const tabs = document.querySelector('.tabs');
        const collapseIcon = collapseBtn?.querySelector('.collapse-icon');

        if (collapseBtn && tabs) {
            collapseBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent event bubbling but allow default behavior
                tabs.classList.toggle('collapsed');

                // Rotate icon when collapsed
                if (collapseIcon) {
                    if (tabs.classList.contains('collapsed')) {
                        collapseIcon.style.transform = 'rotate(180deg)';
                    } else {
                        collapseIcon.style.transform = 'rotate(0deg)';
                    }
                }
            });
        } else {
            console.warn('Navigation collapse button or tabs not found');
        }
    } catch (error) {
        console.error('Error setting up navigation collapse:', error);
    }
}

// API helpers
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        if (!response.ok) {
            let errorDetail = response.statusText;
            try {
                const errorJson = await response.json();
                errorDetail = errorJson.detail || errorJson.message || response.statusText;
            } catch (e) {
                // If response is not JSON, use statusText
            }
            throw new Error(`API error: ${errorDetail}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        alert(`Error: ${error.message}`);
        throw error;
    }
}

// Orders
let currentOrderView = 'all'; // 'all' or 'unfinished'

function switchOrderView(view) {
    console.log('switchOrderView called with view:', view);

    // Always update the view, even if it's the same
    currentOrderView = view;

    // Update stat pill buttons
    const allBtn = document.getElementById('all-orders-pill');
    const unfinishedBtn = document.getElementById('unfinished-orders-pill');

    if (allBtn && unfinishedBtn) {
        // Remove active class from both
        allBtn.classList.remove('active');
        unfinishedBtn.classList.remove('active');

        // Add active class to the selected button
        if (view === 'all') {
            allBtn.classList.add('active');
        } else if (view === 'unfinished') {
            unfinishedBtn.classList.add('active');
        }
    } else {
        console.error('Could not find stat pill buttons!', { allBtn, unfinishedBtn });
    }

    console.log('Current view set to:', currentOrderView);
    console.log('Reloading orders...');

    // Force reload orders with the new view
    loadOrders();
}

// Make sure function is accessible globally for onclick handlers
if (typeof window !== 'undefined') {
    window.switchOrderView = switchOrderView;
}

// Switch route view (all routes vs unscheduled)
function switchRouteView(view) {
    // Update tab buttons
    document.querySelectorAll('#all-routes-btn, #unscheduled-routes-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        }
    });

    // Filter routes based on view
    if (view === 'unscheduled') {
        // Show only unscheduled routes (routes with pending orders)
        // This would need to filter the displayed routes
        loadPlannedRoutes();
    } else {
        // Show all routes
        loadPlannedRoutes();
    }
}

async function loadOrders() {
    const status = document.getElementById('order-status-filter')?.value || '';
    const source = document.getElementById('order-source-filter')?.value || '';

    // Fetch all orders for counting
    let allOrdersUrl = '/orders';
    const allParams = [];
    if (status) allParams.push(`status=${status}`);
    if (source) allParams.push(`source=${source}`);
    if (allParams.length) allOrdersUrl += '?' + allParams.join('&');

    try {
        // Fetch all orders first to get accurate counts
        const allOrders = await apiCall(allOrdersUrl);

        // Determine which orders to display based on view
        let ordersToDisplay = allOrders;
        if (currentOrderView === 'unfinished') {
            // Fetch unfinished orders from backend
            let unfinishedUrl = '/orders';
            const unfinishedParams = [];
            if (status) unfinishedParams.push(`status=${status}`);
            if (source) unfinishedParams.push(`source=${source}`);
            unfinishedParams.push('unfinished=true');
            unfinishedUrl += '?' + unfinishedParams.join('&');
            ordersToDisplay = await apiCall(unfinishedUrl);
        } else {
            // For 'all' view (now called "Orders"), show only finished orders
            // Filter out unfinished orders client-side
            ordersToDisplay = allOrders.filter(order => {
                const hasErrors = order.validation_errors && order.validation_errors.length > 0;
                const isUnfinished = hasErrors || !order.delivery_address || order.delivery_address.trim() === '';
                return !isUnfinished; // Only finished orders
            });
        }

        displayOrders(allOrders, ordersToDisplay);
    } catch (error) {
        console.error('Failed to load orders:', error);
        alert(`Failed to load orders: ${error.message}`);
    }
}

function displayOrders(allOrders, ordersToDisplay) {
    const container = document.getElementById('orders-list');

    // If ordersToDisplay not provided, use allOrders
    ordersToDisplay = ordersToDisplay || allOrders || [];
    allOrders = allOrders || ordersToDisplay || [];

    // Calculate counts from all orders
    const finishedOrdersCount = allOrders.filter(order => {
        const hasErrors = order.validation_errors && order.validation_errors.length > 0;
        const isUnfinished = hasErrors || !order.delivery_address || order.delivery_address.trim() === '';
        return !isUnfinished; // Finished orders
    }).length;

    const unfinishedOrdersCount = allOrders.filter(order => {
        const hasErrors = order.validation_errors && order.validation_errors.length > 0;
        const isUnfinished = hasErrors || !order.delivery_address || order.delivery_address.trim() === '';
        return isUnfinished;
    }).length;

    // Update count badges
    const allCountEl = document.getElementById('all-orders-count');
    const unfinishedCountEl = document.getElementById('unfinished-orders-count');

    if (allCountEl) allCountEl.textContent = finishedOrdersCount; // Show count of finished orders
    if (unfinishedCountEl) unfinishedCountEl.textContent = unfinishedOrdersCount;

    // Sort orders by created_at (newest first)
    let sortedOrders = [...ordersToDisplay];
    if (sortedOrders.length > 0) {
        sortedOrders.sort((a, b) => {
            const aDate = new Date(a.created_at || 0);
            const bDate = new Date(b.created_at || 0);
            return bDate - aDate; // Newest first
        });
    }

    if (!sortedOrders || sortedOrders.length === 0) {
        container.innerHTML = '<p>No orders found</p>';
        return;
    }

    container.innerHTML = sortedOrders.map(order => {
        const priorityClass = order.priority || 'normal';
        const timeWindow = order.delivery_time_window_start && order.delivery_time_window_end
            ? `${new Date(order.delivery_time_window_start).toLocaleString()} - ${new Date(order.delivery_time_window_end).toLocaleString()}`
            : 'No time restriction';

        const hasErrors = order.validation_errors && order.validation_errors.length > 0;
        const isUnfinished = hasErrors || !order.delivery_address || order.delivery_address.trim() === '';

        return `
        <div class="order-card ${order.status} ${isUnfinished ? 'unfinished-order' : ''}">
            <div class="order-card-content">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                    <h3>${order.order_number || `Order #${order.id}`}</h3>
                    <div style="display: flex; gap: 5px; align-items: center;">
                        ${isUnfinished ? '<span class="badge" style="background: #f8d7da; color: #721c24;">⚠️ UNFINISHED</span>' : ''}
                        <span class="badge priority-${priorityClass}">${(order.priority || 'normal').toUpperCase()}</span>
                    </div>
                </div>
                <p><strong>Address:</strong> ${order.delivery_address || '<span style="color: red;">MISSING</span>'}</p>
                ${order.description ? `<p><strong>Description:</strong> ${order.description}</p>` : ''}
                ${order.customer_name ? `<p><strong>Customer:</strong> ${order.customer_name}</p>` : ''}
                ${order.customer_phone ? `<p><strong>Phone:</strong> ${order.customer_phone}</p>` : ''}
                <p><strong>Status:</strong> <span class="badge ${order.status}">${order.status}</span></p>
                <p><strong>Delivery Window:</strong> ${timeWindow}</p>
                ${order.source ? `<p><strong>Source:</strong> ${order.source}</p>` : ''}
                ${order.items && order.items.length > 0 ?
                    `<p><strong>Items:</strong> ${order.items.map(i => `${i.quantity}x ${i.name}`).join(', ')}</p>` : ''}
                ${hasErrors ?
                    `<div style="background: #f8d7da; padding: 10px; border-radius: 4px; margin-top: 10px;">
                        <strong style="color: #721c24;">⚠️ Validation Errors:</strong>
                        <ul style="margin: 5px 0; padding-left: 20px; color: #721c24;">
                            ${order.validation_errors.map(err => `<li>${err}</li>`).join('')}
                        </ul>
                    </div>` : ''}
            </div>
            <div class="order-card-actions">
                <button class="btn btn-secondary" onclick="editOrder(${order.id})">Edit</button>
                <button class="btn btn-danger" onclick="deleteOrder(${order.id})">Delete</button>
            </div>
        </div>
    `;
    }).join('');
}

function showAddOrderModal() {
    showModal(`
        <h2>Add New Order</h2>
        <form id="add-order-form" onsubmit="addOrder(event)">
            <div class="form-group">
                <label>Delivery Address *</label>
                <input type="text" name="delivery_address" required>
            </div>
            <div class="form-group">
                <label>Customer Name</label>
                <input type="text" name="customer_name">
            </div>
            <div class="form-group">
                <label>Customer Phone</label>
                <input type="tel" name="customer_phone">
            </div>
            <div class="form-group">
                <label>Customer Email</label>
                <input type="email" name="customer_email">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea name="description" rows="3" placeholder="Order description or special instructions"></textarea>
            </div>
            <div class="form-group">
                <label>Delivery Time Window Start</label>
                <input type="datetime-local" name="delivery_time_window_start">
                <small>Leave empty for no time restriction (low priority)</small>
            </div>
            <div class="form-group">
                <label>Delivery Time Window End</label>
                <input type="datetime-local" name="delivery_time_window_end">
                <small>Priority will be auto-calculated based on time window</small>
            </div>
            <div class="form-group">
                <label>Priority</label>
                <select name="priority">
                    <option value="">Auto (based on time window)</option>
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                </select>
            </div>
            <div class="form-group">
                <label>Source</label>
                <select name="source">
                    <option value="phone">Phone</option>
                    <option value="email">Email</option>
                    <option value="fax">Fax</option>
                    <option value="mail">Mail</option>
                </select>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Order</button>
            </div>
        </form>
    `);
}

async function addOrder(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    // Convert datetime-local strings to ISO format
    if (data.delivery_time_window_start) {
        data.delivery_time_window_start = new Date(data.delivery_time_window_start).toISOString();
    }
    if (data.delivery_time_window_end) {
        data.delivery_time_window_end = new Date(data.delivery_time_window_end).toISOString();
    }

    // Remove priority if empty (will be auto-calculated)
    if (!data.priority || data.priority === '') {
        delete data.priority;
    }

    try {
        await apiCall('/orders', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal();
        loadOrders();
    } catch (error) {
        console.error('Failed to add order:', error);
    }
}

function showUploadModal() {
    showModal(`
        <h2>Upload Order Document</h2>
        <form id="upload-form" onsubmit="uploadOrder(event)">
            <div class="form-group">
                <label>Source</label>
                <select name="source">
                    <option value="email">Email</option>
                    <option value="fax">Fax</option>
                    <option value="mail">Mail</option>
                </select>
            </div>
            <div class="form-group">
                <label>Upload File</label>
                <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg" required>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Upload & Parse</button>
            </div>
        </form>
    `);
}

async function uploadOrder(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const source = formData.get('source');
    const file = formData.get('file');

    if (!file) {
        alert('Please select a file to upload');
        return;
    }

    try {
        const uploadForm = new FormData();
        uploadForm.append('file', file);
        uploadForm.append('source', source);

        const response = await fetch(`${API_BASE}/orders/upload`, {
            method: 'POST',
            body: uploadForm
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
        }

        const order = await response.json();
        closeModal();
        loadOrders();
        if (order.validation_errors && order.validation_errors.length > 0) {
            alert(`Order parsed but has validation errors: ${order.validation_errors.join(', ')}`);
        } else {
            alert(`Order uploaded successfully! Order ID: ${order.id}`);
        }
    } catch (error) {
        alert(`Upload failed: ${error.message}`);
        console.error('Upload error:', error);
    }
}

async function editOrder(id) {
    try {
        const order = await apiCall(`/orders/${id}`);
        showEditOrderModal(order);
    } catch (error) {
        console.error('Failed to load order:', error);
        alert(`Failed to load order: ${error.message}`);
    }
}

function showEditOrderModal(order) {
    // Format datetime-local values from ISO strings
    const formatDateTimeLocal = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    };

    showModal(`
        <h2>Edit Order</h2>
        <form id="edit-order-form" onsubmit="updateOrder(event, ${order.id})">
            <div class="form-group">
                <label>Order Number</label>
                <input type="text" name="order_number" value="${order.order_number || ''}">
            </div>
            <div class="form-group">
                <label>Delivery Address *</label>
                <input type="text" name="delivery_address" value="${order.delivery_address || ''}" required>
            </div>
            <div class="form-group">
                <label>Customer Name</label>
                <input type="text" name="customer_name" value="${order.customer_name || ''}">
            </div>
            <div class="form-group">
                <label>Customer Phone</label>
                <input type="tel" name="customer_phone" value="${order.customer_phone || ''}">
            </div>
            <div class="form-group">
                <label>Customer Email</label>
                <input type="email" name="customer_email" value="${order.customer_email || ''}">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea name="description" rows="3" placeholder="Order description or special instructions">${order.description || ''}</textarea>
            </div>
            <div class="form-group">
                <label>Delivery Time Window Start</label>
                <input type="datetime-local" name="delivery_time_window_start" value="${formatDateTimeLocal(order.delivery_time_window_start)}">
                <small>Leave empty for no time restriction (low priority)</small>
            </div>
            <div class="form-group">
                <label>Delivery Time Window End</label>
                <input type="datetime-local" name="delivery_time_window_end" value="${formatDateTimeLocal(order.delivery_time_window_end)}">
                <small>Priority will be auto-calculated based on time window</small>
            </div>
            <div class="form-group">
                <label>Priority</label>
                <select name="priority">
                    <option value="" ${!order.priority ? 'selected' : ''}>Auto (based on time window)</option>
                    <option value="low" ${order.priority === 'low' ? 'selected' : ''}>Low</option>
                    <option value="normal" ${order.priority === 'normal' ? 'selected' : ''}>Normal</option>
                    <option value="high" ${order.priority === 'high' ? 'selected' : ''}>High</option>
                    <option value="urgent" ${order.priority === 'urgent' ? 'selected' : ''}>Urgent</option>
                </select>
            </div>
            <div class="form-group">
                <label>Status</label>
                <select name="status">
                    <option value="pending" ${order.status === 'pending' ? 'selected' : ''}>Pending</option>
                    <option value="assigned" ${order.status === 'assigned' ? 'selected' : ''}>Assigned</option>
                    <option value="in_transit" ${order.status === 'in_transit' ? 'selected' : ''}>In Transit</option>
                    <option value="completed" ${order.status === 'completed' ? 'selected' : ''}>Completed</option>
                </select>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Order</button>
            </div>
        </form>
    `);
}

async function updateOrder(event, id) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    // Convert datetime-local strings to ISO format
    if (data.delivery_time_window_start) {
        data.delivery_time_window_start = new Date(data.delivery_time_window_start).toISOString();
    } else {
        data.delivery_time_window_start = null;
    }
    if (data.delivery_time_window_end) {
        data.delivery_time_window_end = new Date(data.delivery_time_window_end).toISOString();
    } else {
        data.delivery_time_window_end = null;
    }

    // Remove priority if empty (will be auto-calculated)
    if (!data.priority || data.priority === '') {
        delete data.priority;
    }

    // Remove empty fields
    Object.keys(data).forEach(key => {
        if (data[key] === '' || data[key] === null) {
            delete data[key];
        }
    });

    try {
        await apiCall(`/orders/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        closeModal();
        loadOrders();
    } catch (error) {
        console.error('Failed to update order:', error);
        alert(`Failed to update order: ${error.message}`);
    }
}

async function deleteOrder(id) {
    if (!confirm('Are you sure you want to delete this order?')) return;
    try {
        await apiCall(`/orders/${id}`, { method: 'DELETE' });
        loadOrders();
    } catch (error) {
        console.error('Failed to delete order:', error);
    }
}

// Drivers
async function loadDrivers() {
    try {
        const drivers = await apiCall('/drivers');
        displayDrivers(drivers);
    } catch (error) {
        console.error('Failed to load drivers:', error);
    }
}

function displayDrivers(drivers) {
    const container = document.getElementById('drivers-list');
    if (!drivers || drivers.length === 0) {
        container.innerHTML = '<p>No drivers found</p>';
        return;
    }

    container.innerHTML = drivers.map(driver => `
        <div class="driver-card">
            <h3>${driver.name}</h3>
            ${driver.phone ? `<p><strong>Phone:</strong> ${driver.phone}</p>` : ''}
            ${driver.email ? `<p><strong>Email:</strong> ${driver.email}</p>` : ''}
            <p><strong>Status:</strong> ${driver.status}</p>
            <div style="margin-top: 10px;">
                <button class="btn btn-secondary" onclick="editDriver(${driver.id})">Edit</button>
                <button class="btn btn-danger" onclick="deleteDriver(${driver.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

function showAddDriverModal() {
    showModal(`
        <h2>Add New Driver</h2>
        <form id="add-driver-form" onsubmit="addDriver(event)">
            <div class="form-group">
                <label>Name *</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Phone</label>
                <input type="tel" name="phone">
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email">
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Driver</button>
            </div>
        </form>
    `);
}

async function addDriver(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    try {
        await apiCall('/drivers', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal();
        loadDrivers();
    } catch (error) {
        console.error('Failed to add driver:', error);
    }
}

async function editDriver(id) {
    try {
        const driver = await apiCall(`/drivers/${id}`);
        showEditDriverModal(driver);
    } catch (error) {
        console.error('Failed to load driver:', error);
        alert(`Failed to load driver: ${error.message}`);
    }
}

function showEditDriverModal(driver) {
    showModal(`
        <h2>Edit Driver</h2>
        <form id="edit-driver-form" onsubmit="updateDriver(event, ${driver.id})">
            <div class="form-group">
                <label>Name *</label>
                <input type="text" name="name" value="${driver.name || ''}" required>
            </div>
            <div class="form-group">
                <label>Phone</label>
                <input type="tel" name="phone" value="${driver.phone || ''}">
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email" value="${driver.email || ''}">
            </div>
            <div class="form-group">
                <label>Status</label>
                <select name="status">
                    <option value="available" ${driver.status === 'available' ? 'selected' : ''}>Available</option>
                    <option value="on_route" ${driver.status === 'on_route' ? 'selected' : ''}>On Route</option>
                    <option value="offline" ${driver.status === 'offline' ? 'selected' : ''}>Offline</option>
                </select>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Update Driver</button>
            </div>
        </form>
    `);
}

async function updateDriver(event, id) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    // Remove empty fields
    Object.keys(data).forEach(key => {
        if (data[key] === '' || data[key] === null) {
            delete data[key];
        }
    });

    try {
        await apiCall(`/drivers/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        closeModal();
        loadDrivers();
    } catch (error) {
        console.error('Failed to update driver:', error);
        alert(`Failed to update driver: ${error.message}`);
    }
}

async function deleteDriver(id) {
    if (!confirm('Are you sure you want to delete this driver?')) return;
    try {
        await apiCall(`/drivers/${id}`, { method: 'DELETE' });
        loadDrivers();
    } catch (error) {
        console.error('Failed to delete driver:', error);
    }
}

// Routes
async function loadRoutes() {
    try {
        const routes = await apiCall('/routes');
        displayRoutes(routes);
    } catch (error) {
        console.error('Failed to load routes:', error);
    }
}

function displayRoutes(routes) {
    const container = document.getElementById('routes-list');
    if (!routes || routes.length === 0) {
        container.innerHTML = '<p>No routes found. Create a route and add orders to it.</p>';
        return;
    }

    container.innerHTML = routes.map(route => `
        <div class="route-card">
            <h3>Route #${route.id} - ${route.name || 'Unnamed'}</h3>
            <p><strong>Status:</strong> <span class="status-badge status-${route.status}">${route.status}</span></p>
            <div style="margin-top: 10px; display: flex; gap: 5px; flex-wrap: wrap;">
                <button class="btn btn-primary" onclick="viewRoute(${route.id})">🗺️ View on Map</button>
                <button class="btn btn-secondary" onclick="optimizeRoute(${route.id})">⚡ Optimize</button>
                <button class="btn btn-secondary" onclick="editRoute(${route.id})">✏️ Edit</button>
                <button class="btn btn-danger" onclick="deleteRoute(${route.id})">🗑️ Delete</button>
            </div>
        </div>
    `).join('');
}

async function showCreateRouteModal() {
    try {
        const [drivers, orders] = await Promise.all([
            apiCall('/drivers'),
            apiCall('/orders?status=pending')
        ]);

        const driversOptions = drivers.map(d =>
            `<option value="${d.id}">${d.name} (${d.status})</option>`
        ).join('');

        const ordersOptions = orders.map(o =>
            `<option value="${o.id}">${o.order_number || o.id} - ${o.delivery_address}</option>`
        ).join('');

        showModal(`
            <h2>Create New Route</h2>
            <form id="create-route-form" onsubmit="createRoute(event)">
                <div class="form-group">
                    <label>Route Name</label>
                    <input type="text" name="name" placeholder="Route Name (optional)">
                </div>
                <div class="form-group">
                    <label>Driver *</label>
                    <select name="driver_id" required>
                        <option value="">Select a driver</option>
                        ${driversOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Select Orders (hold Ctrl/Cmd to select multiple)</label>
                    <select name="order_ids" multiple size="8" required style="min-height: 150px;">
                        ${ordersOptions || '<option disabled>No pending orders available</option>'}
                    </select>
                    <small style="color: #666;">Select multiple orders to add to this route</small>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Create Route</button>
                </div>
            </form>
        `);
    } catch (error) {
        alert(`Failed to load data: ${error.message}`);
    }
}

async function createRoute(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const driverId = formData.get('driver_id');
    const routeName = formData.get('name') || `Route ${new Date().toLocaleDateString()}`;
    const orderIds = Array.from(formData.getAll('order_ids')).map(id => parseInt(id));

    if (!driverId || orderIds.length === 0) {
        alert('Please select a driver and at least one order');
        return;
    }

    try {
        // Create route
        const route = await apiCall('/routes', {
            method: 'POST',
            body: JSON.stringify({
                driver_id: parseInt(driverId),
                name: routeName
            })
        });

        // Add orders to route
        const orderItems = orderIds.map((orderId, index) => ({
            order_id: orderId,
            sequence: index + 1
        }));

        await apiCall(`/routes/${route.id}/orders`, {
            method: 'POST',
            body: JSON.stringify(orderItems)
        });

        closeModal();
        loadRoutes();
        alert('Route created successfully! Click "Optimize" to calculate the best route.');
    } catch (error) {
        alert(`Failed to create route: ${error.message}`);
    }
}

async function editRoute(routeId) {
    try {
        const route = await apiCall(`/routes/${routeId}`);
        const [drivers, allOrders] = await Promise.all([
            apiCall('/drivers'),
            apiCall('/orders')
        ]);

        const currentOrderIds = route.route_orders?.map(ro => ro.order_id) || [];

        const driversOptions = drivers.map(d =>
            `<option value="${d.id}" ${d.id === route.driver_id ? 'selected' : ''}>${d.name}</option>`
        ).join('');

        const ordersOptions = allOrders.map(o =>
            `<option value="${o.id}" ${currentOrderIds.includes(o.id) ? 'selected' : ''}>${o.order_number || o.id} - ${o.delivery_address}</option>`
        ).join('');

        showModal(`
            <h2>Edit Route #${route.id}</h2>
            <form id="edit-route-form" onsubmit="updateRoute(event, ${routeId})">
                <div class="form-group">
                    <label>Route Name</label>
                    <input type="text" name="name" value="${route.name || ''}" placeholder="Route Name">
                </div>
                <div class="form-group">
                    <label>Driver</label>
                    <select name="driver_id">
                        ${driversOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Orders (hold Ctrl/Cmd to select multiple)</label>
                    <select name="order_ids" multiple size="8" style="min-height: 150px;">
                        ${ordersOptions}
                    </select>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Update Route</button>
                </div>
            </form>
        `);
    } catch (error) {
        alert(`Failed to load route: ${error.message}`);
    }
}

async function updateRoute(event, routeId) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const driverId = formData.get('driver_id');
    const routeName = formData.get('name');
    const orderIds = Array.from(formData.getAll('order_ids')).map(id => parseInt(id));

    try {
        // Update route
        await apiCall(`/routes/${routeId}`, {
            method: 'PUT',
            body: JSON.stringify({
                driver_id: parseInt(driverId),
                name: routeName
            })
        });

        // Update orders
        const orderItems = orderIds.map((orderId, index) => ({
            order_id: orderId,
            sequence: index + 1
        }));

        await apiCall(`/routes/${routeId}/orders`, {
            method: 'POST',
            body: JSON.stringify(orderItems)
        });

        closeModal();
        loadRoutes();
        alert('Route updated successfully!');
    } catch (error) {
        alert(`Failed to update route: ${error.message}`);
    }
}

async function optimizeRoute(routeId) {
    try {
        const result = await apiCall(`/routes/${routeId}/optimize`, { method: 'POST' });

        // Show optimization results
        const metrics = result.optimization_metrics || {};
        const summary = result.route_summary || {};
        let message = 'Route optimized successfully!';

        if (metrics.distance_improvement_percent) {
            message += `\nDistance improved by ${metrics.distance_improvement_percent.toFixed(1)}%`;
        }
        if (summary.total_distance_km) {
            message += `\nNew total distance: ${summary.total_distance_km.toFixed(2)}km`;
        }

        alert(message);

        // Reload routes to show updated data
        loadPlannedRoutes();

        // If this route is currently selected, refresh the map view
        const selectedCard = document.querySelector(`.route-card[data-route-id="${routeId}"].selected`);
        if (selectedCard) {
            viewRoute(routeId);
        }
    } catch (error) {
        console.error('Route optimization error:', error);
        alert(`Optimization failed: ${error.message || 'Unknown error'}`);
    }
}

// Make function globally accessible
if (typeof window !== 'undefined') {
    window.optimizeRoute = optimizeRoute;
}

async function manageRouteOrders(routeId) {
    try {
        // Get route details with orders
        const route = await apiCall(`/routes/${routeId}`);

        // Get all orders (not just pending, to include already assigned ones)
        const allOrders = await apiCall('/orders');

        // Get current route orders
        const currentOrderIds = route.route_orders ? route.route_orders.map(ro => ro.order_id) : [];
        const currentOrders = [];
        const availableOrders = [];

        // Separate current and available orders
        for (const order of allOrders) {
            if (currentOrderIds.includes(order.id)) {
                // This order is in the current route
                currentOrders.push(order);
            } else if (!order.assigned_driver_id || order.status === 'pending' || order.status === 'assigned') {
                // This order is available to be added (unassigned or can be reassigned)
                availableOrders.push(order);
            }
        }

        // Sort current orders by sequence
        if (route.route_orders) {
            currentOrders.sort((a, b) => {
                const roA = route.route_orders.find(ro => ro.order_id === a.id);
                const roB = route.route_orders.find(ro => ro.order_id === b.id);
                return (roA?.sequence || 0) - (roB?.sequence || 0);
            });
        }

        // Create modal HTML
        const modalHTML = `
            <h2>Manage Route Orders</h2>
            <div style="margin-bottom: 20px;">
                <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--text-primary);">Current Orders (${currentOrders.length})</h3>
                <div id="current-orders-list" style="max-height: 200px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; background: var(--bg-secondary);">
                    ${currentOrders.length > 0 ? currentOrders.map((order, idx) => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px; margin-bottom: 8px; background: var(--card-bg); border-radius: 6px;">
                            <div style="flex: 1;">
                                <div style="font-weight: 600; color: var(--text-primary);">${order.order_number || `Order #${order.id}`}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">${order.delivery_address || 'No address'}</div>
                            </div>
                            <button onclick="removeOrderFromRoute(${order.id})" style="padding: 6px 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">Remove</button>
                        </div>
                    `).join('') : '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No orders in route</p>'}
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--text-primary);">Available Orders (${availableOrders.length})</h3>
                <div id="available-orders-list" style="max-height: 200px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; background: var(--bg-secondary);">
                    ${availableOrders.length > 0 ? availableOrders.map(order => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px; margin-bottom: 8px; background: var(--card-bg); border-radius: 6px;">
                            <div style="flex: 1;">
                                <div style="font-weight: 600; color: var(--text-primary);">${order.order_number || `Order #${order.id}`}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">${order.delivery_address || 'No address'}</div>
                            </div>
                            <button onclick="addOrderToRoute(${order.id})" style="padding: 6px 12px; background: var(--accent-primary); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">Add</button>
                        </div>
                    `).join('') : '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No available orders</p>'}
                </div>
            </div>

            <div class="form-actions" style="display: flex; gap: 12px; margin-top: 24px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="saveRouteOrders(${routeId})">Save Changes</button>
                <button type="button" class="btn btn-primary" onclick="saveAndOptimizeRoute(${routeId})" style="background: var(--accent-primary);">Save & Optimize</button>
            </div>
        `;

        showModal(modalHTML);

        // Store current state for management
        window.currentRouteOrders = currentOrderIds;
        window.currentRouteId = routeId;

    } catch (error) {
        console.error('Failed to load route orders:', error);
        alert(`Failed to load route orders: ${error.message}`);
    }
}

function addOrderToRoute(orderId) {
    if (!window.currentRouteOrders) {
        window.currentRouteOrders = [];
    }
    if (!window.currentRouteOrders.includes(orderId)) {
        window.currentRouteOrders.push(orderId);
        // Update UI
        const addBtn = event.target;
        const orderItem = addBtn.closest('div[style*="display: flex"]');
        if (orderItem) {
            addBtn.textContent = 'Added';
            addBtn.disabled = true;
            addBtn.style.background = '#10b981';
        }
    }
}

function removeOrderFromRoute(orderId) {
    if (window.currentRouteOrders) {
        window.currentRouteOrders = window.currentRouteOrders.filter(id => id !== orderId);
        // Update UI
        const removeBtn = event.target;
        const orderItem = removeBtn.closest('div[style*="display: flex"]');
        if (orderItem) {
            orderItem.style.opacity = '0.5';
            removeBtn.textContent = 'Removed';
            removeBtn.disabled = true;
        }
    }
}

async function saveRouteOrders(routeId) {
    try {
        const orderIds = window.currentRouteOrders || [];

        // Create route order items with sequence
        const orderItems = orderIds.map((orderId, index) => ({
            order_id: orderId,
            sequence: index + 1
        }));

        await apiCall(`/routes/${routeId}/orders`, {
            method: 'POST',
            body: JSON.stringify(orderItems)
        });

        alert('Route orders updated successfully!');
        closeModal();
        loadPlannedRoutes();

        // Refresh map if route is selected
        const selectedCard = document.querySelector(`.route-card[data-route-id="${routeId}"].selected`);
        if (selectedCard) {
            viewRoute(routeId);
        }
    } catch (error) {
        console.error('Failed to save route orders:', error);
        alert(`Failed to save route orders: ${error.message}`);
    }
}

async function saveAndOptimizeRoute(routeId) {
    try {
        // First save the orders
        await saveRouteOrders(routeId);

        // Then optimize
        await optimizeRoute(routeId);
    } catch (error) {
        console.error('Failed to save and optimize route:', error);
        alert(`Failed to save and optimize route: ${error.message}`);
    }
}

// Make functions globally accessible
if (typeof window !== 'undefined') {
    window.manageRouteOrders = manageRouteOrders;
    window.addOrderToRoute = addOrderToRoute;
    window.removeOrderFromRoute = removeOrderFromRoute;
    window.saveRouteOrders = saveRouteOrders;
    window.saveAndOptimizeRoute = saveAndOptimizeRoute;
}

async function viewRoute(routeId) {
    try {
        // Ensure routes tab is active and map is visible
        const routesTab = document.getElementById('routes-tab');
        if (!routesTab || !routesTab.classList.contains('active')) {
            // Switch to routes tab first
            document.querySelector('[data-tab="routes"]')?.click();
            // Wait for tab to be visible
            await new Promise(resolve => setTimeout(resolve, 300));
        }

        // Get route visualization data
        const routeData = await apiCall(`/routes/${routeId}/visualize`);
        console.log('Route data received:', routeData);
        currentRouteData = routeData; // Store for timeline interactions
        displayRouteOnMap(routeData);

        // If timeline view is active, update it
        const timelineBtn = document.querySelector('.view-btn[data-view="timeline"]');
        if (timelineBtn && timelineBtn.classList.contains('active')) {
            loadTimelineView(routeId);
        }
    } catch (error) {
        console.error('Failed to load route:', error);
        alert(`Failed to load route visualization: ${error.message}`);
    }
}

function displayRouteOnMap(routeData, routeColor = null, routeIndex = 0, retryCount = 0) {
    console.log('Displaying route on map:', routeData);

    if (retryCount > 5) {
        console.error('Failed to initialize map after multiple retries');
        alert('Could not initialize map. Please reload the page.');
        return;
    }

    if (!routeMap) {
        // Initialize map if not already done
        console.log('Map not initialized, initializing now...');
        initRouteMap();
        // Wait a bit for map to initialize
        setTimeout(() => {
            console.log('Retrying display after map init');
            displayRouteOnMap(routeData, routeColor, routeIndex, retryCount + 1);
        }, 500);
        return;
    }

    // Double-check map is ready
    if (!routeMap || !routeMap.getContainer()) {
        console.error('Map container not ready');
        setTimeout(() => displayRouteOnMap(routeData, routeColor, routeIndex, retryCount + 1), 300);
        return;
    }

    // Ensure map size is correct before displaying
    // Force container to be visible and have dimensions
    const routeMapElement = document.getElementById('route-map');
    if (routeMapElement) {
        const container = routeMapElement.parentElement;
        if (container) {
            container.style.display = 'block';
            container.style.height = '600px';
            console.log('Map container dimensions:', container.offsetWidth, 'x', container.offsetHeight);
        }
    }

    // Wait a bit to ensure container is fully visible, then invalidate
    setTimeout(() => {
        if (routeMap) {
            routeMap.invalidateSize();
            console.log('Map size invalidated after delay');
        }
    }, 200);

    // Clear all existing route layers
    currentRouteLayers.forEach(layer => {
        try {
            routeMap.removeLayer(layer);
        } catch (e) {
            console.warn('Error removing layer:', e);
        }
    });
    currentRouteMarkers = [];
    currentRouteLayers = [];

    if (!routeData.waypoints || routeData.waypoints.length === 0) {
        alert('No waypoints found in route');
        return;
    }

    // Create custom icons for different waypoint types
    const createIcon = (color, type) => {
        const iconHtml = type === 'depot' ? '🏭' : type === 'parking' ? '🅿️' : '📦';
        return L.divIcon({
            className: 'custom-marker',
            html: `<div style="background-color: ${color}; border: 3px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.4); z-index: 2000; position: relative;">${iconHtml}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
    };

    // Add waypoints with color-coded markers
    const waypointMarkers = [];
    console.log(`Adding ${routeData.waypoints.length} waypoints to map`);
    routeData.waypoints.forEach((waypoint, index) => {
        // Handle both 'lng' and 'lon' field names for compatibility
        const lng = waypoint.lng || waypoint.lon;
        if (!waypoint.lat || !lng) {
            console.warn('Waypoint missing coordinates:', waypoint);
            return;
        }
        console.log(`Adding waypoint ${index + 1}: ${waypoint.type} at [${waypoint.lat}, ${lng}]`);
        const waypointColor = waypoint.color || (routeColor ? routeColor : (waypoint.type === 'depot' ? '#FF0000' : waypoint.type === 'parking' ? '#FFA500' : '#008000'));
        const icon = createIcon(waypointColor, waypoint.type);
        const marker = L.marker([waypoint.lat, lng], {
            icon,
            zIndexOffset: 2000,
            riseOnHover: true
        }).addTo(routeMap);

        // Create popup content
        let popupContent = `<strong>${waypoint.type.toUpperCase()}</strong><br>`;
        if (waypoint.type === 'depot') {
            popupContent += `Depot: ${routeData.route_name || 'Main Depot'}<br>`;
        } else if (waypoint.type === 'parking') {
            popupContent += `Parking: ${waypoint.metadata?.name || 'Parking Spot'}<br>`;
            if (waypoint.metadata?.distance_to_delivery_km) {
                popupContent += `Distance to delivery: ${waypoint.metadata.distance_to_delivery_km.toFixed(2)} km<br>`;
            }
        } else if (waypoint.type === 'delivery') {
            popupContent += `Order: ${waypoint.metadata?.order_number || 'N/A'}<br>`;
            popupContent += `Address: ${waypoint.metadata?.delivery_address || 'N/A'}<br>`;
            if (waypoint.metadata?.customer_name) {
                popupContent += `Customer: ${waypoint.metadata.customer_name}<br>`;
            }
        }
        popupContent += `Sequence: ${index + 1}`;
        if (waypoint.estimated_arrival) {
            const arrival = new Date(waypoint.estimated_arrival);
            popupContent += `<br>ETA: ${arrival.toLocaleTimeString()}`;
        }

        marker.bindPopup(popupContent);
        waypointMarkers.push(marker);
        currentRouteMarkers.push(marker);
        currentRouteLayers.push(marker);
    });

    // Draw route - use OSRM geometry if available (real road routes), otherwise use segments
    const hasOsrmGeometry = routeData.geometry && routeData.geometry.coordinates && routeData.geometry.coordinates.length > 0;

    if (hasOsrmGeometry) {
        console.log('Using OSRM geometry for route display');
        // Use OSRM route geometry (GeoJSON LineString) - this shows actual roads!
        try {
            const routeLineColor = routeColor || '#0066cc';
            const routeLayer = L.geoJSON(routeData.geometry, {
                style: {
                    color: routeLineColor,
                    weight: 5,
                    opacity: 0.8
                }
            }).addTo(routeMap);
            currentRouteLayers.push(routeLayer);

            // Add direction arrows along the route
            const coordinates = routeData.geometry.coordinates;
            if (coordinates && coordinates.length > 1) {
                // Add arrows at regular intervals
                const arrowInterval = Math.max(1, Math.floor(coordinates.length / 15));
                for (let i = arrowInterval; i < coordinates.length - 1; i += arrowInterval) {
                    const [lng1, lat1] = coordinates[i - 1];
                    const [lng2, lat2] = coordinates[i];
                    const midLat = (lat1 + lat2) / 2;
                    const midLng = (lng1 + lng2) / 2;

                    const bearing = getBearing({ lat: lat1, lng: lng1 }, { lat: lat2, lng: lng2 });
                    // Arrow character points right (0°), so we need to rotate it by the bearing
                    // Also add 90° because the arrow starts pointing east, but we want it to point in the direction of travel
                    const arrowRotation = bearing;
                    const arrowColor = routeColor || '#0066cc';
                    const arrowIcon = L.divIcon({
                        className: 'route-arrow',
                        html: `<div style="color: ${arrowColor}; font-size: 20px; transform: rotate(${arrowRotation}deg); transform-origin: center; display: inline-block; width: 20px; height: 20px; text-align: center; line-height: 20px;">➤</div>`,
                        iconSize: [20, 20],
                        iconAnchor: [10, 10]
                    });

                    const arrowMarker = L.marker([midLat, midLng], { icon: arrowIcon, interactive: false, zIndexOffset: 1000 })
                        .addTo(routeMap);
                    currentRouteLayers.push(arrowMarker);
                }
            }
        } catch (e) {
            console.warn('Error displaying OSRM geometry, falling back to segments:', e);
            // Fall through to segment drawing
        }
    }

    // Fallback: Draw route segments with color coding (straight lines between waypoints)
    if (!hasOsrmGeometry && routeData.segments && routeData.segments.length > 0) {
        console.log('Using fallback straight-line segments (OSRM geometry not available)');
        routeData.segments.forEach((segment, index) => {
            const fromWaypoint = routeData.waypoints[index];
            const toWaypoint = routeData.waypoints[index + 1];

            // Determine segment color based on destination type
            const segmentColor = toWaypoint.color;
            const segmentWeight = 4;

            const fromLng = segment.from.lng || segment.from.lon;
            const toLng = segment.to.lng || segment.to.lon;
            const polyline = L.polyline(
                [
                    [segment.from.lat, fromLng],
                    [segment.to.lat, toLng]
                ],
                {
                    color: segmentColor,
                    weight: segmentWeight,
                    opacity: 0.7,
                    dashArray: toWaypoint.type === 'parking' ? '5, 5' : null // Dashed line for parking segments
                }
            ).addTo(routeMap);
            currentRouteLayers.push(polyline);

            // Add direction arrow in the middle of the segment
            const midLat = (segment.from.lat + segment.to.lat) / 2;
            // fromLng and toLng are already defined above
            const midLng = (fromLng + toLng) / 2;
            const bearing = getBearing({ lat: segment.from.lat, lng: fromLng }, { lat: segment.to.lat, lng: toLng });

            // Create arrow marker
            const arrowIcon = L.divIcon({
                className: 'route-arrow',
                html: `<div style="color: ${segmentColor}; font-size: 20px; transform: rotate(${bearing}deg); transform-origin: center; display: inline-block; width: 20px; height: 20px; text-align: center; line-height: 20px;">➤</div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });

            const arrowMarker = L.marker([midLat, midLng], { icon: arrowIcon, interactive: false, zIndexOffset: 1000 })
                .addTo(routeMap);
            currentRouteLayers.push(arrowMarker);
        });
    } else if (!routeData.geometry) {
        // Final fallback: draw simple polyline connecting all waypoints
        const latlngs = routeData.waypoints.map(w => {
            const lng = w.lng || w.lon;
            return [w.lat, lng];
        }).filter(coord => coord[0] && coord[1]);
        const fallbackColor = routeColor || '#0066cc';
        const fallbackPolyline = L.polyline(latlngs, {
            color: fallbackColor,
            weight: 4,
            opacity: 0.7
        }).addTo(routeMap);
        currentRouteLayers.push(fallbackPolyline);
    }

    // Fit map to show all waypoints
    if (waypointMarkers.length > 0) {
        try {
            const group = new L.featureGroup(waypointMarkers);
            const bounds = group.getBounds();
            console.log('Fitting map to bounds:', bounds);
            routeMap.fitBounds(bounds.pad(0.1));
        } catch (e) {
            console.error('Error fitting bounds:', e);
            // Fallback: set view to first waypoint
            if (waypointMarkers.length > 0) {
                const firstMarker = waypointMarkers[0];
                routeMap.setView([firstMarker.getLatLng().lat, firstMarker.getLatLng().lng], 13);
            }
        }
    } else {
        console.warn('No waypoint markers to fit bounds');
    }

    // Update statistics bar with route data
    updateRouteStatistics(routeData.summary, hasOsrmGeometry);

    // Display route legend on map (only legend, not full summary)
    const legendHtml = `
        <div style="background: #ffffff; padding: 12px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); max-width: 200px; border: 1px solid #e0e0e0; position: absolute; top: 10px; right: 10px; z-index: 1000;">
            <p style="margin: 5px 0; font-size: 12px; color: #131320; font-weight: 600;"><strong>Legend:</strong></p>
                <p style="margin: 2px 0; font-size: 12px; color: #131320;"><span style="color: ${routeData.colors.depot};">●</span> Depot</p>
                <p style="margin: 2px 0; font-size: 12px; color: #131320;"><span style="color: ${routeData.colors.parking};">●</span> Parking</p>
                <p style="margin: 2px 0; font-size: 12px; color: #131320;"><span style="color: ${routeData.colors.delivery};">●</span> Delivery</p>
        </div>
    `;

    // Remove existing legend if any
    const existingLegend = document.getElementById('route-legend');
    if (existingLegend) {
        existingLegend.remove();
    }

    // Add legend to map container
    const mapContainerDiv = document.getElementById('route-map-container');
    if (mapContainerDiv) {
        const legendDiv = document.createElement('div');
        legendDiv.id = 'route-legend';
        legendDiv.innerHTML = legendHtml;
        mapContainerDiv.appendChild(legendDiv);
    }
}

// Helper function to calculate bearing for arrow direction
function getBearing(from, to) {
    const lat1 = from.lat * Math.PI / 180;
    const lat2 = to.lat * Math.PI / 180;
    const dLon = (to.lng - from.lng) * Math.PI / 180;

    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);

    const bearing = Math.atan2(y, x) * 180 / Math.PI;
    return (bearing + 360) % 360;
}

async function deleteRoute(id) {
    if (!confirm('Are you sure you want to delete this route?')) return;
    try {
        await apiCall(`/routes/${id}`, { method: 'DELETE' });
        loadRoutes();
    } catch (error) {
        console.error('Failed to delete route:', error);
    }
}

// Locations
async function loadDepots() {
    try {
        const depots = await apiCall('/locations/depots');
        displayDepots(depots);
    } catch (error) {
        console.error('Failed to load depots:', error);
    }
}

function displayDepots(depots) {
    const container = document.getElementById('depots-list');
    if (!depots || depots.length === 0) {
        container.innerHTML = '<p>No depots found</p>';
        return;
    }

    container.innerHTML = depots.map(depot => `
        <div class="location-card">
            <h4>${depot.name}</h4>
            <p>${depot.address}</p>
            <button class="btn btn-danger" onclick="deleteDepot(${depot.id})">Delete</button>
        </div>
    `).join('');
}

async function loadParkingLocations() {
    try {
        const parking = await apiCall('/locations/parking');
        displayParkingLocations(parking);
    } catch (error) {
        console.error('Failed to load parking locations:', error);
    }
}

function displayParkingLocations(parking) {
    const container = document.getElementById('parking-list');
    if (!parking || parking.length === 0) {
        container.innerHTML = '<p>No parking locations found</p>';
        return;
    }

    container.innerHTML = parking.map(p => `
        <div class="location-card">
            <h4>${p.name || 'Unnamed'}</h4>
            <p>${p.address}</p>
            <button class="btn btn-danger" onclick="deleteParking(${p.id})">Delete</button>
        </div>
    `).join('');
}

function showAddDepotModal() {
    showModal(`
        <h2>Add Depot</h2>
        <form id="add-depot-form" onsubmit="addDepot(event)">
            <div class="form-group">
                <label>Name *</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Address *</label>
                <input type="text" name="address" required>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Depot</button>
            </div>
        </form>
    `);
}

async function addDepot(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    try {
        await apiCall('/locations/depots', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal();
        loadDepots();
    } catch (error) {
        console.error('Failed to add depot:', error);
    }
}

function showAddParkingModal() {
    showModal(`
        <h2>Add Parking Location</h2>
        <form id="add-parking-form" onsubmit="addParking(event)">
            <div class="form-group">
                <label>Name</label>
                <input type="text" name="name">
            </div>
            <div class="form-group">
                <label>Address *</label>
                <input type="text" name="address" required>
            </div>
            <div class="form-group">
                <label>Notes</label>
                <textarea name="notes"></textarea>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Parking</button>
            </div>
        </form>
    `);
}

async function addParking(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.fromEntries(formData);

    try {
        await apiCall('/locations/parking', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeModal();
        loadParkingLocations();
    } catch (error) {
        console.error('Failed to add parking location:', error);
    }
}

async function deleteDepot(id) {
    if (!confirm('Are you sure you want to delete this depot?')) return;
    try {
        await apiCall(`/locations/depots/${id}`, { method: 'DELETE' });
        loadDepots();
    } catch (error) {
        console.error('Failed to delete depot:', error);
    }
}

async function deleteParking(id) {
    if (!confirm('Are you sure you want to delete this parking location?')) return;
    try {
        await apiCall(`/locations/parking/${id}`, { method: 'DELETE' });
        loadParkingLocations();
    } catch (error) {
        console.error('Failed to delete parking location:', error);
    }
}

// Map
function initRouteMap() {
    // Check if map already exists
    if (routeMap) {
        routeMap.remove();
        routeMap = null;
    }

    // Ensure map container is visible and has dimensions
    const routeMapElement = document.getElementById('route-map');
    if (!routeMapElement) {
        console.error('Map container not found');
        return;
    }

    // Ensure container is visible
    const routesTab = document.getElementById('routes-tab');
    if (routesTab && !routesTab.classList.contains('active')) {
        console.warn('Routes tab is not active, map may not display correctly');
    }

    console.log('Initializing map container:', routeMapElement.offsetWidth, 'x', routeMapElement.offsetHeight);

    // Set initial view to Heilbronn depot location
    routeMap = L.map('route-map', {
        preferCanvas: false, // Use canvas for better performance
        zoomControl: true
    }).setView([49.1372, 9.2074], 13);

    // Use a more reliable tile layer with retry logic
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
        tileSize: 256,
        zoomOffset: 0,
        retry: 3,
        crossOrigin: true
    });

    osmLayer.addTo(routeMap);

    // Invalidate size after a short delay to ensure proper rendering
    setTimeout(() => {
        if (routeMap) {
            routeMap.invalidateSize();
        }
    }, 200);
}

// Modal
function showModal(content) {
    document.getElementById('modal-body').innerHTML = content;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// Phone Call Demo
let mediaRecorder = null;
let audioChunks = [];
let recordingInterval = null;
let isRecording = false;
let fullTranscription = '';
let transcriptionChunks = [];

function showPhoneCallModal() {
    // Reset state
    audioChunks = [];
    fullTranscription = '';
    transcriptionChunks = [];
    isRecording = false;

    showModal(`
        <h2>📞 Simulate Phone Call</h2>
        <div id="phone-call-interface">
            <div style="margin-bottom: 20px;">
                <p style="color: #666; margin-bottom: 15px;">
                    Click "Start Recording" to begin. Speak as if you're a customer placing an order.
                    The transcription will appear after you stop recording.
                </p>
                <div id="recording-status" style="padding: 10px; border-radius: 4px; background: #f0f0f0; margin-bottom: 15px;">
                    <strong>Status:</strong> <span id="status-text">Ready to record</span>
                </div>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <button id="start-recording-btn" class="btn btn-primary" onclick="startRecording()">🎤 Start Recording</button>
                    <button id="stop-recording-btn" class="btn btn-danger" onclick="stopRecording()" disabled>⏹ Stop Recording</button>
                    <button id="clear-btn" class="btn btn-secondary" onclick="clearRecording()">🗑 Clear</button>
                </div>
            </div>
            <div id="review-section" style="display: none; margin-top: 20px;">
                <h3>Review & Create Order</h3>
                <div style="margin-bottom: 15px;">
                    <label><strong>Final Transcription:</strong></label>
                    <textarea id="final-transcription" rows="6" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 14px;" readonly></textarea>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-primary" onclick="parseAndCreateOrder()">📝 Parse & Create Order</button>
                    <button class="btn btn-secondary" onclick="editTranscription()">✏️ Edit Transcription</button>
                </div>
            </div>
        </div>
    `);
}

async function startRecording() {
    try {
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Initialize MediaRecorder
        const options = { mimeType: 'audio/webm' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            options.mimeType = 'audio/webm;codecs=opus';
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = ''; // Use default
            }
        }

        mediaRecorder = new MediaRecorder(stream, options);
        audioChunks = [];
        transcriptionChunks = [];
        fullTranscription = '';

        // Accumulate chunks - only send complete files when recording stops
        // Note: MediaRecorder chunks don't form valid WebM files until recording is stopped
        mediaRecorder.ondataavailable = async (event) => {
            console.log('Data available event fired, size:', event.data.size);
            if (event.data.size > 0) {
                // Just accumulate chunks - don't send during recording
                // WebM files need proper structure that MediaRecorder creates on stop
                audioChunks.push(event.data);
                console.log(`Accumulated ${audioChunks.length} chunks, total size: ${audioChunks.reduce((sum, chunk) => sum + chunk.size, 0)} bytes`);
            }
        };

        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            alert('Recording error: ' + event.error.message);
        };

        // Update UI
        document.getElementById('start-recording-btn').disabled = true;
        document.getElementById('stop-recording-btn').disabled = false;
        document.getElementById('status-text').textContent = '🔴 Recording...';
        document.getElementById('recording-status').style.background = '#fee';

        // Reset transcription state
        fullTranscription = '';
        transcriptionChunks = [];

        // Hide review section when starting new recording
        const reviewSection = document.getElementById('review-section');
        if (reviewSection) {
            reviewSection.style.display = 'none';
        }

        // Start recording - request data every 1 second (for accumulation)
        // We'll send complete files every 5 seconds
        isRecording = true;
        mediaRecorder.start(1000);  // Request chunks every 1 second for smoother accumulation
        console.log('Recording started, MediaRecorder state:', mediaRecorder.state);

    } catch (error) {
        console.error('Error starting recording:', error);
        alert(`Failed to start recording: ${error.message}\n\nPlease ensure you grant microphone permissions.`);
    }
}

async function processAudioChunkBlob(audioBlob) {
    if (!audioBlob || audioBlob.size === 0) {
        console.log('Empty audio blob, skipping');
        return;
    }

    console.log('Processing audio blob, size:', audioBlob.size);

    // Update status
    const statusText = document.getElementById('status-text');
    if (statusText && isRecording) {
        statusText.textContent = '⏳ Processing transcription...';
    }

    try {
        // Send to backend for transcription
        const formData = new FormData();
        formData.append('audio', audioBlob, 'chunk.webm');

        console.log('Sending audio to backend for transcription...');
        const response = await fetch(`${API_BASE}/orders/transcribe-audio`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            let errorMessage = `Transcription failed: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                const errorText = await response.text();
                if (errorText) {
                    errorMessage = errorText;
                }
            }
            console.error('Transcription API error:', response.status, errorMessage);
            throw new Error(errorMessage);
        }

        const result = await response.json();
        console.log('Transcription result:', result);

        if (result.success) {
            const transcribedText = result.transcription ? result.transcription.trim() : '';

            if (transcribedText) {
                // Add to transcription chunks
                transcriptionChunks.push(transcribedText);
                fullTranscription = transcriptionChunks.join(' ');
                console.log('Updated transcription:', fullTranscription);
            } else {
                console.log('Empty transcription received (might be silence or too short)');
            }
        } else {
            console.log('Transcription failed in result');
            throw new Error('Transcription failed');
        }

        // Update status back to recording
        if (statusText && isRecording) {
            statusText.textContent = '🔴 Recording...';
        }

    } catch (error) {
        console.error('Error processing audio chunk:', error);

        // Extract user-friendly error message
        let userMessage = 'Unable to transcribe the audio. Please try recording again.';
        if (error.message) {
            // Use the error message from backend (which is now user-friendly)
            userMessage = error.message;
        }

        if (statusText) {
            statusText.textContent = '❌ Transcription failed: ' + userMessage;
        }

        // Show review section even on error, with error message
        const reviewSection = document.getElementById('review-section');
        const finalTranscription = document.getElementById('final-transcription');
        if (reviewSection && finalTranscription) {
            finalTranscription.value = fullTranscription || '';
            reviewSection.style.display = 'block';
        }
    }
}

async function stopRecording() {
    if (!mediaRecorder || !isRecording) return;

    isRecording = false;

    // Stop interval
    if (recordingInterval) {
        clearInterval(recordingInterval);
        recordingInterval = null;
    }

    // Add a one-time handler for when recording stops
    const stopHandler = async () => {
        console.log('Stop handler called, processing final recording...');

        // Update status to show we're processing
        const statusText = document.getElementById('status-text');
        if (statusText) {
            statusText.textContent = '⏳ Processing transcription...';
        }

        // Wait for MediaRecorder to fully finalize (all dataavailable events fired)
        await new Promise(resolve => setTimeout(resolve, 500));

        // Process final complete recording
        // Create blob from all accumulated chunks - MediaRecorder should have finalized them
        if (audioChunks.length > 0) {
            console.log('Processing final recording with', audioChunks.length, 'chunks');
            const finalBlob = new Blob(audioChunks, { type: 'audio/webm' });
            console.log('Final blob size:', finalBlob.size, 'bytes');

            // Validate blob has minimum size
            if (finalBlob.size < 4096) {
                console.warn('Recording too short, skipping transcription');
                if (statusText) {
                    statusText.textContent = '⚠️ Recording too short. Please record for at least a few seconds.';
                }
                audioChunks = [];
                return;
            }

            try {
                console.log('Sending complete recording for transcription...');
                await processAudioChunkBlob(finalBlob);
            } catch (error) {
                console.error('Transcription error:', error);
                // Error handling is done in processAudioChunkBlob
            }
            audioChunks = [];
        } else {
            console.warn('No audio chunks recorded');
            if (statusText) {
                statusText.textContent = '⚠️ No audio recorded. Please try again.';
            }
        }

        // Stop all tracks
        if (mediaRecorder && mediaRecorder.stream) {
            mediaRecorder.stream.getTracks().forEach(track => {
                track.stop();
                console.log('Stopped track:', track.kind);
            });
        }

        // Update UI
        document.getElementById('start-recording-btn').disabled = false;
        document.getElementById('stop-recording-btn').disabled = true;
        document.getElementById('recording-status').style.background = '#efe';

        // Show review section with final transcription
        const reviewSection = document.getElementById('review-section');
        const finalTranscription = document.getElementById('final-transcription');
        if (reviewSection && finalTranscription) {
            finalTranscription.value = fullTranscription || '';
            reviewSection.style.display = 'block';
            console.log('Final transcription:', fullTranscription);

            // Update status
            if (statusText) {
                if (fullTranscription) {
                    statusText.textContent = '✅ Recording complete';
                } else {
                    statusText.textContent = '⚠️ No transcription available';
                }
            }
        }
    };

    // If recording, stop it and wait for the stop event
    if (mediaRecorder.state === 'recording' || mediaRecorder.state === 'paused') {
        console.log('Stopping MediaRecorder, current state:', mediaRecorder.state);
        // Request final data chunk before stopping
        try {
            mediaRecorder.requestData();
        } catch (e) {
            console.warn('Could not request final data:', e);
        }
        // Set up stop handler - this will be called after MediaRecorder finalizes
        mediaRecorder.onstop = stopHandler;
        mediaRecorder.stop();
    } else {
        // Already stopped or inactive
        console.log('MediaRecorder already stopped, state:', mediaRecorder.state);
        await stopHandler();
    }
}

function clearRecording() {
    // Stop any active recording
    if (isRecording) {
        stopRecording();
    }

    // Reset state
    audioChunks = [];
    fullTranscription = '';
    transcriptionChunks = [];

    // Update UI
    const display = document.getElementById('transcription-display');
    if (display) {
        display.textContent = 'No transcription yet...';
    }

    const finalTranscription = document.getElementById('final-transcription');
    if (finalTranscription) {
        finalTranscription.value = '';
    }

    const reviewSection = document.getElementById('review-section');
    if (reviewSection) {
        reviewSection.style.display = 'none';
    }

    document.getElementById('status-text').textContent = 'Ready to record';
    document.getElementById('recording-status').style.background = '#f0f0f0';
}

function editTranscription() {
    const finalTranscription = document.getElementById('final-transcription');
    if (finalTranscription) {
        finalTranscription.readOnly = false;
        finalTranscription.style.border = '2px solid #3498db';
    }
}

async function parseAndCreateOrder() {
    const finalTranscription = document.getElementById('final-transcription');
    if (!finalTranscription || !finalTranscription.value.trim()) {
        alert('No transcription to parse. Please record audio first.');
        return;
    }

    const transcriptionText = finalTranscription.value.trim();

    try {
        // Show loading state
        const parseBtn = event?.target || document.querySelector('button[onclick="parseAndCreateOrder()"]');
        if (parseBtn) {
            parseBtn.disabled = true;
            parseBtn.textContent = '⏳ Parsing...';
        }

        // Parse the transcription
        const response = await fetch(`${API_BASE}/orders/parse-text`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: transcriptionText,
                source: 'phone'
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Parsing failed' }));
            throw new Error(errorData.detail || `Parsing failed with status ${response.status}`);
        }

        const order = await response.json();

        // Check if order is unfinished (has validation errors or missing required fields)
        const hasErrors = order.validation_errors && order.validation_errors.length > 0;
        const isUnfinished = hasErrors || !order.delivery_address || order.delivery_address.trim() === '';

        // Close phone call modal
        closeModal();

        // Reload orders to show the new order
        loadOrders();

        // If unfinished, switch to unfinished view and show message
        if (isUnfinished) {
            switchOrderView('unfinished');
            setTimeout(() => {
                const message = hasErrors
                    ? `Order created but marked as UNFINISHED.\n\nMissing information:\n${order.validation_errors.map(err => `• ${err}`).join('\n')}\n\nPlease edit the order to add missing information or call the customer.`
                    : `Order created but marked as UNFINISHED.\n\nMissing required information (Delivery Address).\n\nPlease edit the order to add missing information or call the customer.`;
                alert(message);
                // Show edit modal for the unfinished order
                showEditOrderModal(order);
            }, 300);
        } else {
            // Order is complete - show success message
            setTimeout(() => {
                alert(`✅ Order #${order.order_number || order.id} created successfully!\n\nAll required information is present.`);
            }, 100);
        }

    } catch (error) {
        console.error('Error parsing order:', error);
        alert(`Failed to parse order: ${error.message}\n\nPlease try again or manually create the order.`);
    } finally {
        // Reset button state
        const parseBtn = event?.target || document.querySelector('button[onclick="parseAndCreateOrder()"]');
        if (parseBtn) {
            parseBtn.disabled = false;
            parseBtn.textContent = '📝 Parse & Create Order';
        }
    }
}

// ==================== NEW ROUTE PLANNING UI ====================

let plannedRoutes = [];
let currentDate = new Date();
let allRoutes = [];

// Initialize route planning UI when routes tab is shown
function initRoutePlanningUI() {
    updateDateDisplay();
    setupDateNavigation();
    setupPlanRoutesButton();
    loadRouteStatistics();
    loadPlannedRoutes();
    setupDepotsButton();
    setupTimelineViewToggle();
    setupTimelineCollapse();
}

// Update date display
function updateDateDisplay() {
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        const options = { weekday: 'short', month: 'short', day: 'numeric' };
        dateElement.textContent = currentDate.toLocaleDateString('en-US', options);
    }
}

// Setup date navigation
function setupDateNavigation() {
    const prevBtn = document.getElementById('date-prev');
    const nextBtn = document.getElementById('date-next');

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            currentDate.setDate(currentDate.getDate() - 1);
            updateDateDisplay();
            loadPlannedRoutes();
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            currentDate.setDate(currentDate.getDate() + 1);
            updateDateDisplay();
            loadPlannedRoutes();
        });
    }
}

// Setup plan routes button
function setupPlanRoutesButton() {
    const planBtn = document.getElementById('plan-routes-btn');
    if (planBtn) {
        planBtn.addEventListener('click', () => {
            planRoutesAutomatically();
        });
    }
}

// Plan routes automatically
async function planRoutesAutomatically() {
    try {
        const planBtn = document.getElementById('plan-routes-btn');
        if (planBtn) {
            planBtn.disabled = true;
            planBtn.textContent = 'Planning...';
        }

        // Use today's date or null (which allows all pending orders)
        const dateStr = currentDate ? currentDate.toISOString().split('T')[0] : null;

        const response = await apiCall('/routes/plan', {
            method: 'POST',
            body: JSON.stringify({
                date: dateStr,  // Can be null to get all pending orders
                max_distance_km: 10.0,
                min_orders_per_route: 3,
                max_orders_per_route: 40,
                clustering_method: 'dbscan',
                assignment_strategy: 'balanced'
            })
        });

        plannedRoutes = response.routes || [];

        // Update statistics
        updateStatistics(response.statistics);

        // Ensure packages stat is visible
        const packagesEl = document.getElementById('stat-packages');
        if (packagesEl) {
            const packagesItem = packagesEl.closest('.stat-item');
            if (packagesItem) {
                packagesItem.style.display = 'flex';
            }
        }

        // Update scheduled/unscheduled counts
        updateOrderCounts(response.statistics);

        // Display routes
        displayPlannedRoutes(plannedRoutes);

        // Routes are now only displayed when clicked, not automatically
        // Timeline is now shown when route is selected, no need to update here

        if (planBtn) {
            planBtn.disabled = false;
            planBtn.textContent = 'Plan Routes';
        }

        alert(`Successfully planned ${plannedRoutes.length} routes!`);
    } catch (error) {
        console.error('Route planning failed:', error);
        alert(`Route planning failed: ${error.message}`);

        const planBtn = document.getElementById('plan-routes-btn');
        if (planBtn) {
            planBtn.disabled = false;
            planBtn.textContent = 'Plan Routes';
        }
    }
}

// Update statistics bar
function updateStatistics(stats) {
    if (!stats) return;

    const driversEl = document.getElementById('stat-drivers');
    const packagesEl = document.getElementById('stat-packages');
    const distanceEl = document.getElementById('stat-distance');
    const timeEl = document.getElementById('stat-time');
    const depotsEl = document.getElementById('stat-depots');

    if (driversEl) driversEl.textContent = stats.drivers_used || 0;
    if (packagesEl) {
        packagesEl.textContent = stats.total_orders || 0;
        // Ensure packages stat is visible
        const packagesItem = packagesEl.closest('.stat-item');
        if (packagesItem) {
            packagesItem.style.display = 'flex';
        }
    }
    if (distanceEl) distanceEl.textContent = `${stats.total_distance_km || 0}km`;

    if (timeEl) {
        const hours = Math.floor((stats.total_time_minutes || 0) / 60);
        const minutes = Math.round((stats.total_time_minutes || 0) % 60);
        timeEl.textContent = `${hours}h ${minutes}m`;
    }

    if (depotsEl) depotsEl.textContent = '1';

    // Hide route-specific stats
    hideRouteStatistics();
}

// Update statistics bar with route-specific data
function updateRouteStatistics(summary, hasOsrmGeometry) {
    const distanceEl = document.getElementById('stat-distance');
    const timeEl = document.getElementById('stat-time');
    const packagesEl = document.getElementById('stat-packages');
    const stopsEl = document.getElementById('stat-stops');
    const stopsValueEl = document.getElementById('stat-stops-value');
    const routingEl = document.getElementById('stat-routing');
    const routingLabelEl = document.getElementById('stat-routing-label');

    if (distanceEl && summary) {
        distanceEl.textContent = `${summary.total_distance_km.toFixed(2)}km`;
    }

    if (timeEl && summary) {
        const hours = Math.floor(summary.total_time_minutes / 60);
        const minutes = Math.round(summary.total_time_minutes % 60);
        timeEl.textContent = `${hours}h ${minutes}m`;
    }

    // Update packages stat with delivery count when route is selected
    if (packagesEl && summary) {
        packagesEl.textContent = summary.delivery_count || 0;
        // Ensure packages stat is visible
        const packagesItem = packagesEl.closest('.stat-item');
        if (packagesItem) {
            packagesItem.style.display = 'flex';
        }
    }

    if (stopsEl && stopsValueEl && summary) {
        stopsValueEl.textContent = summary.waypoint_count || 0;
        stopsEl.style.display = 'flex';
    }

    if (routingEl && routingLabelEl) {
        routingLabelEl.textContent = hasOsrmGeometry ? '🛣️ Real roads' : '📏 Straight lines';
        routingEl.style.display = 'flex';
    }
}

// Hide route-specific statistics
function hideRouteStatistics() {
    const stopsEl = document.getElementById('stat-stops');
    const routingEl = document.getElementById('stat-routing');

    if (stopsEl) stopsEl.style.display = 'none';
    if (routingEl) routingEl.style.display = 'none';
}

// Update order counts (scheduled/unscheduled)
function updateOrderCounts(stats) {
    const unscheduledEl = document.getElementById('unscheduled-count');
    const scheduledEl = document.getElementById('scheduled-count');

    if (unscheduledEl) unscheduledEl.textContent = stats.unscheduled_orders || 0;
    if (scheduledEl) scheduledEl.textContent = stats.total_orders || 0;
}

// Load route statistics
async function loadRouteStatistics() {
    try {
        const routes = await apiCall('/routes?status=planned');
        allRoutes = routes;

        let totalOrders = 0;
        let totalDistance = 0;
        let totalTime = 0;
        const driversUsed = new Set();

        for (const route of routes) {
            if (route.route_orders) {
                totalOrders += route.route_orders.length;
            }
            driversUsed.add(route.driver_id);
        }

        updateStatistics({
            drivers_used: driversUsed.size,
            total_orders: totalOrders,
            total_distance_km: totalDistance,
            total_time_minutes: totalTime,
            unscheduled_orders: 0
        });
    } catch (error) {
        console.error('Failed to load route statistics:', error);
    }
}

// Load planned routes
async function loadPlannedRoutes() {
    try {
        // Load routes, optionally filtered by driver
        let endpoint = '/routes?status=planned';
        if (selectedDriverId !== null) {
            endpoint = `/routes?status=planned&driver_id=${selectedDriverId}`;
        }
        const routes = await apiCall(endpoint);

        // Enrich routes with full details including distances
        const enrichedRoutes = await Promise.all(
            routes.map(async (route) => {
                try {
                    // Get full route details to calculate distance
                    const routeDetails = await apiCall(`/routes/${route.id}/visualize`);
                    // Distance is in summary.total_distance_km
                    const distance = routeDetails.summary?.total_distance_km ||
                                   routeDetails.total_distance_km ||
                                   routeDetails.distance_km || 0;

                    return {
                        ...route,
                        distance_km: distance,
                        total_distance_km: distance,
                        estimated_distance_km: distance
                    };
                } catch (error) {
                    console.warn(`Failed to get distance for route ${route.id}:`, error);
                    // Return route without distance if visualization fails
                    return {
                        ...route,
                        distance_km: 0,
                        total_distance_km: 0,
                        estimated_distance_km: 0
                    };
                }
            })
        );

        allRoutes = enrichedRoutes;
        displayPlannedRoutes(enrichedRoutes);
        // Routes are now only displayed when clicked, not automatically
        // Timeline is now shown when route is selected
    } catch (error) {
        console.error('Failed to load planned routes:', error);
    }
}

// Load drivers for routes page
async function loadDriversForRoutes() {
    try {
        const drivers = await apiCall('/drivers');
        allDrivers = drivers;
        displayDriversForRoutes(drivers);
    } catch (error) {
        console.error('Failed to load drivers:', error);
    }
}

// Display drivers on routes page
function displayDriversForRoutes(drivers) {
    const container = document.getElementById('drivers-list-routes');
    if (!container) return;

    if (!drivers || drivers.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No drivers available</p>';
        return;
    }

    container.innerHTML = drivers.map(driver => {
        const isSelected = selectedDriverId === driver.id;
        return `
            <div class="driver-card-routes ${isSelected ? 'selected' : ''}" data-driver-id="${driver.id}" onclick="selectDriverForRoutes(${driver.id})">
                <div class="driver-avatar">👤</div>
                <div class="driver-info-routes">
                    <div class="driver-name-routes">${driver.name}</div>
                    <div class="driver-status-routes">${driver.status || 'available'}</div>
                </div>
            </div>
        `;
    }).join('');
}

// Select driver and filter routes
function selectDriverForRoutes(driverId) {
    // Toggle selection
    if (selectedDriverId === driverId) {
        selectedDriverId = null; // Deselect
    } else {
        selectedDriverId = driverId; // Select
    }

    // Update driver cards UI
    document.querySelectorAll('.driver-card-routes').forEach(card => {
        if (parseInt(card.dataset.driverId) === selectedDriverId) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });

    // Reload routes with filter
    loadPlannedRoutes();
}

// Make function globally accessible
if (typeof window !== 'undefined') {
    window.selectDriverForRoutes = selectDriverForRoutes;
}

// Display planned routes in the routes list panel
function displayPlannedRoutes(routes) {
    const container = document.getElementById('routes-list-container');
    if (!container) return;

    container.innerHTML = '';

    // Filter routes by selected driver if any
    let filteredRoutes = routes;
    if (selectedDriverId !== null) {
        filteredRoutes = routes.filter(route => route.driver_id === selectedDriverId);
    }

    if (!filteredRoutes || filteredRoutes.length === 0) {
        const message = selectedDriverId
            ? '<div class="empty-state">No routes assigned to this driver.</div>'
            : '<div class="empty-state">No routes planned. Click "Plan Routes" to create routes automatically.</div>';
        container.innerHTML = message;
        return;
    }

    filteredRoutes.forEach((route, index) => {
        const routeCard = document.createElement('div');
        const routeId = route.id || route.route_id || index;
        routeCard.className = 'route-card';
        routeCard.dataset.routeId = routeId;

        const color = route.color || getRouteColor(index);
        const routeName = route.route_name || route.name || `Route ${index + 1}`;

        // Get order count - prioritize order_count field
        let orderCount = 0;
        if (route.order_count !== undefined && route.order_count !== null) {
            orderCount = route.order_count;
        } else if (route.route_orders && Array.isArray(route.route_orders)) {
            orderCount = route.route_orders.length;
        } else if (route.order_ids && Array.isArray(route.order_ids)) {
            orderCount = route.order_ids.length;
        }

        // Get distance - try multiple fields, default to 0 if not found
        let distance = 0;
        if (route.total_distance_km !== undefined && route.total_distance_km !== null) {
            distance = route.total_distance_km;
        } else if (route.distance_km !== undefined && route.distance_km !== null) {
            distance = route.distance_km;
        } else if (route.estimated_distance_km !== undefined && route.estimated_distance_km !== null) {
            distance = route.estimated_distance_km;
        }

        // Get driver name from allDrivers array if not in route
        let driverName = route.driver_name;
        if (!driverName && route.driver_id && allDrivers.length > 0) {
            const driver = allDrivers.find(d => d.id === route.driver_id);
            if (driver) {
                driverName = driver.name;
            }
        }

        routeCard.innerHTML = `
            <div class="route-color-bar" style="background-color: ${color}"></div>
            <div class="route-info">
                <div class="route-header">
                    <div class="route-name">${routeName}</div>
                    ${driverName ? `<div class="route-driver-badge">👤 ${driverName}</div>` : ''}
                </div>
                <div class="route-stats">
                    <span class="route-stat">📦 ${orderCount}</span>
                    <span class="route-stat">🛣️ ${distance.toFixed(1)}km</span>
                </div>
                <div class="route-actions">
                    <button class="btn-route-optimize" onclick="event.stopPropagation(); optimizeRoute(${routeId})" title="Optimize Route">
                        ⚡ Optimize
                    </button>
                    <button class="btn-route-manage" onclick="event.stopPropagation(); manageRouteOrders(${routeId})" title="Manage Orders">
                        ✏️ Manage Orders
                    </button>
                </div>
            </div>
        `;

        routeCard.addEventListener('click', () => {
            selectRouteCard(route, index);
        });

        container.appendChild(routeCard);
    });
}

// Get route color from palette
function getRouteColor(index) {
    const colors = [
        "#9b59b6", "#e91e63", "#00bcd4", "#4caf50", "#ff9800",
        "#2196f3", "#f44336", "#009688", "#ffc107", "#795548"
    ];
    return colors[index % colors.length];
}

// Select a route card
function selectRouteCard(route, index) {
    document.querySelectorAll('.route-card').forEach(card => {
        card.classList.remove('selected');
    });

    const routeId = route.id || route.route_id || index;
    const routeCard = document.querySelector(`.route-card[data-route-id="${routeId}"]`);
    if (routeCard) {
        routeCard.classList.add('selected');
    }

    // View route on map
    if (route.id || route.route_id) {
        viewRoute(route.id || route.route_id);

        // If timeline view is active, update it
        const timelineBtn = document.querySelector('.view-btn[data-view="timeline"]');
        if (timelineBtn && timelineBtn.classList.contains('active')) {
            loadTimelineView(route.id || route.route_id);
        }
    } else {
        // No route selected - hide timeline and reset stats
        hideTimelineView();
        hideRouteStatistics();
        // Reset distance and time to default
        const distanceEl = document.getElementById('stat-distance');
        const timeEl = document.getElementById('stat-time');
        if (distanceEl) distanceEl.textContent = '0km';
        if (timeEl) timeEl.textContent = '0h 0m';
    }
}

// Display all routes on map simultaneously
async function displayAllRoutesOnMap(routes) {
    if (!routeMap) {
        setTimeout(() => displayAllRoutesOnMap(routes), 500);
        return;
    }

    // Clear existing routes
    if (currentRouteLayers) {
        currentRouteLayers.forEach(layer => {
            routeMap.removeLayer(layer);
        });
    }
    currentRouteLayers = [];
    currentRouteMarkers = [];

    if (!routes || routes.length === 0) {
        return;
    }

    // Load and display each route
    for (let i = 0; i < routes.length; i++) {
        const route = routes[i];
        if (route.id) {
            try {
                const routeData = await apiCall(`/routes/${route.id}/visualize`);
                const color = route.color || getRouteColor(i);
                displayRouteOnMap(routeData, color, i);
            } catch (error) {
                console.error(`Failed to load route ${route.id}:`, error);
            }
        }
    }

    // Fit map to show all routes
    if (currentRouteLayers.length > 0) {
        const group = L.featureGroup(currentRouteLayers);
        routeMap.fitBounds(group.getBounds().pad(0.1));
    }
}

// Old timeline functions removed - timeline is now shown next to routes list

// Setup routes panel collapse functionality
function setupRoutesPanelCollapse() {
    const toggleBtn = document.getElementById('routes-panel-toggle');
    const routesPanel = document.getElementById('routes-list-panel');

    if (toggleBtn && routesPanel) {
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            routesPanel.classList.toggle('collapsed');

            // Update collapse icon
            const collapseIcon = toggleBtn.querySelector('.collapse-icon');
            if (collapseIcon) {
                if (routesPanel.classList.contains('collapsed')) {
                    collapseIcon.textContent = '▶';
                } else {
                    collapseIcon.textContent = '◀';
                }
            }

            // Invalidate map size after collapse/expand
            setTimeout(() => {
                if (routeMap) {
                    routeMap.invalidateSize();
                }
            }, 300);
        });

        // Add click handler to expand button (when collapsed) - using event delegation
        document.addEventListener('click', (e) => {
            if (routesPanel.classList.contains('collapsed')) {
                // Check if click is on the expand button (::after pseudo-element)
                // Since we can't directly detect clicks on ::after, we check if click is near left edge
                const clickX = e.clientX;
                const panelRect = routesPanel.getBoundingClientRect();

                // Expand button is at left edge (x=0 to x=40)
                if (clickX >= 0 && clickX <= 40 && e.target !== toggleBtn) {
                    routesPanel.classList.remove('collapsed');
                    const collapseIcon = toggleBtn.querySelector('.collapse-icon');
                    if (collapseIcon) {
                        collapseIcon.textContent = '◀';
                    }
                    setTimeout(() => {
                        if (routeMap) {
                            routeMap.invalidateSize();
                        }
                    }, 300);
                }
            }
        });
    }
}

// Setup Depots button
function setupDepotsButton() {
    const depotsBtn = document.getElementById('depots-btn');
    if (depotsBtn) {
        depotsBtn.addEventListener('click', () => {
            // Switch to locations tab
            document.querySelector('[data-tab="locations"]')?.click();
        });
    }
}

// Setup timeline view toggle
function setupTimelineViewToggle() {
    const timelineBtn = document.querySelector('.view-btn[data-view="timeline"]');
    if (timelineBtn) {
        timelineBtn.addEventListener('click', () => {
            const isActive = timelineBtn.classList.contains('active');

            if (isActive) {
                // Toggle off
                timelineBtn.classList.remove('active');
                hideTimelineView();
            } else {
                // Toggle on
                timelineBtn.classList.add('active');
                showTimelineView();
            }
        });
    }
}

// Setup timeline collapse functionality
function setupTimelineCollapse() {
    const collapseBtn = document.getElementById('timeline-collapse-btn');
    const timelineView = document.getElementById('routes-timeline-view');

    if (collapseBtn && timelineView) {
        collapseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isCollapsed = timelineView.classList.contains('collapsed');

            if (isCollapsed) {
                // Expand
                timelineView.classList.remove('collapsed');
                const collapseIcon = collapseBtn.querySelector('.collapse-icon');
                if (collapseIcon) {
                    collapseIcon.textContent = '▶';
                }
            } else {
                // Collapse
                timelineView.classList.add('collapsed');
                const collapseIcon = collapseBtn.querySelector('.collapse-icon');
                if (collapseIcon) {
                    collapseIcon.textContent = '◀';
                }
            }
        });
    }
}

// Show timeline view (next to routes list)
function showTimelineView() {
    const timelineView = document.getElementById('routes-timeline-view');

    if (timelineView) {
        // Show timeline view
        timelineView.style.display = 'flex';

        // Load timeline data for selected route
        const selectedRouteCard = document.querySelector('.route-card.selected');
        if (selectedRouteCard) {
            const routeId = selectedRouteCard.dataset.routeId;
            if (routeId) {
                loadTimelineView(parseInt(routeId));
            } else {
                // If no route selected, show empty state
                const content = document.getElementById('timeline-view-content');
                if (content) {
                    content.innerHTML = '<div class="timeline-error">Select a route to view timeline</div>';
                }
            }
        } else {
            // If no route selected, show empty state
            const content = document.getElementById('timeline-view-content');
            if (content) {
                content.innerHTML = '<div class="timeline-error">Select a route to view timeline</div>';
            }
        }
    }
}

// Hide timeline view
function hideTimelineView() {
    const timelineView = document.getElementById('routes-timeline-view');

    if (timelineView) {
        timelineView.style.display = 'none';
    }
}

// Load timeline view with stop-to-stop data
async function loadTimelineView(routeId) {
    try {
        const routeData = await apiCall(`/routes/${routeId}/visualize`);
        displayTimelineView(routeData);
    } catch (error) {
        console.error('Failed to load timeline view:', error);
        const content = document.getElementById('timeline-view-content');
        if (content) {
            content.innerHTML = '<div class="timeline-error">Failed to load route timeline</div>';
        }
    }
}

// Display timeline view with stops, distances, and times
function displayTimelineView(routeData) {
    const content = document.getElementById('timeline-view-content');
    if (!content) return;

    if (!routeData.waypoints || routeData.waypoints.length === 0) {
        content.innerHTML = '<div class="timeline-error">No waypoints in route</div>';
        return;
    }

    const waypoints = routeData.waypoints;

    // Calculate distances and times between stops
    const segments = [];
    for (let i = 0; i < waypoints.length - 1; i++) {
        const from = waypoints[i];
        const to = waypoints[i + 1];

        // Calculate distance using Haversine formula
        const distance = calculateHaversineDistance(
            from.lat, from.lng,
            to.lat, to.lng
        );

        // Estimate time (assuming 50 km/h average speed with 1.3x buffer)
        const timeMinutes = (distance / 50) * 60 * 1.3;

        segments.push({
            from,
            to,
            distance_km: distance,
            time_minutes: timeMinutes
        });
    }

    // Build timeline HTML
    let timelineHtml = `
        <div class="timeline-stops-container">
            <div class="timeline-stop-item" data-waypoint-index="0" data-lat="${waypoints[0].lat}" data-lng="${waypoints[0].lng}" data-type="${waypoints[0].type}">
                <div class="stop-icon stop-${waypoints[0].type}">${getStopIcon(waypoints[0].type)}</div>
                <div class="stop-info">
                    <div class="stop-label">${getStopLabel(waypoints[0])}</div>
                    <div class="stop-details">${getStopDetails(waypoints[0])}</div>
                </div>
                <div class="stop-sequence">1</div>
            </div>
    `;

    segments.forEach((segment, index) => {
        const stopIndex = index + 1;
        const stop = segment.to;

        timelineHtml += `
            <div class="timeline-segment">
                <div class="segment-line"></div>
                <div class="segment-info">
                    <span class="segment-distance">${segment.distance_km.toFixed(2)} km</span>
                    <span class="segment-time">${Math.round(segment.time_minutes)} min</span>
                </div>
            </div>
            <div class="timeline-stop-item" data-waypoint-index="${stopIndex}" data-lat="${stop.lat}" data-lng="${stop.lng}" data-type="${stop.type}">
                <div class="stop-icon stop-${stop.type}">${getStopIcon(stop.type)}</div>
                <div class="stop-info">
                    <div class="stop-label">${getStopLabel(stop)}</div>
                    <div class="stop-details">${getStopDetails(stop)}</div>
                </div>
                <div class="stop-sequence">${stopIndex + 1}</div>
            </div>
        `;
    });

    timelineHtml += '</div>';

    content.innerHTML = timelineHtml;

    // Add click handlers to timeline stop items
    content.querySelectorAll('.timeline-stop-item').forEach(item => {
        item.style.cursor = 'pointer';
        item.addEventListener('click', () => {
            const lat = parseFloat(item.dataset.lat);
            const lng = parseFloat(item.dataset.lng);
            const type = item.dataset.type;
            const waypointIndex = parseInt(item.dataset.waypointIndex);
            const waypoint = waypoints[waypointIndex];

            showTimelineStopOnMap(lat, lng, waypoint, routeData);
        });
    });
}

// Helper function to calculate Haversine distance
function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Helper function to get stop icon
function getStopIcon(type) {
    switch(type) {
        case 'depot': return '🏭';
        case 'parking': return '🅿️';
        case 'delivery': return '📦';
        default: return '📍';
    }
}

// Helper function to get stop label
function getStopLabel(waypoint) {
    if (waypoint.type === 'depot') {
        return waypoint.metadata?.name || 'Depot';
    } else if (waypoint.type === 'parking') {
        return waypoint.metadata?.name || 'Parking';
    } else if (waypoint.type === 'delivery') {
        return waypoint.metadata?.order_number || `Order #${waypoint.metadata?.id || ''}`;
    }
    return 'Stop';
}

// Helper function to get stop details
function getStopDetails(waypoint) {
    if (waypoint.type === 'delivery') {
        return waypoint.metadata?.delivery_address || '';
    } else if (waypoint.type === 'parking') {
        return waypoint.metadata?.address || '';
    } else if (waypoint.type === 'depot') {
        return waypoint.metadata?.address || '';
    }
    return '';
}

// Show timeline stop on map with detailed card
function showTimelineStopOnMap(lat, lng, waypoint, routeData) {
    if (!routeMap) return;

    // Center map on the selected stop
    routeMap.setView([lat, lng], 16);

    // Remove existing delivery info card
    if (deliveryInfoCard) {
        deliveryInfoCard.remove();
        deliveryInfoCard = null;
    }

    // Create detailed info card
    let cardHtml = '';

    if (waypoint.type === 'delivery') {
        const metadata = waypoint.metadata || {};
        cardHtml = `
            <div style="background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.3); max-width: 350px; border: 2px solid #008000;">
                <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #131320; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span>📦</span> Delivery Details
                </h3>
                ${metadata.order_number ? `<p style="margin: 8px 0; color: #131320;"><strong>Order Number:</strong> ${metadata.order_number}</p>` : ''}
                ${metadata.delivery_address ? `<p style="margin: 8px 0; color: #131320;"><strong>Address:</strong> ${metadata.delivery_address}</p>` : ''}
                ${metadata.customer_name ? `<p style="margin: 8px 0; color: #131320;"><strong>Customer:</strong> ${metadata.customer_name}</p>` : ''}
                ${metadata.customer_phone ? `<p style="margin: 8px 0; color: #131320;"><strong>Phone:</strong> ${metadata.customer_phone}</p>` : ''}
                ${metadata.customer_email ? `<p style="margin: 8px 0; color: #131320;"><strong>Email:</strong> ${metadata.customer_email}</p>` : ''}
                ${waypoint.estimated_arrival ? `<p style="margin: 8px 0; color: #131320;"><strong>ETA:</strong> ${new Date(waypoint.estimated_arrival).toLocaleString()}</p>` : ''}
                ${metadata.description ? `<p style="margin: 8px 0; color: #131320;"><strong>Description:</strong> ${metadata.description}</p>` : ''}
                ${metadata.priority ? `<p style="margin: 8px 0; color: #131320;"><strong>Priority:</strong> <span style="text-transform: uppercase; color: ${metadata.priority === 'urgent' ? '#dc2626' : metadata.priority === 'high' ? '#ea580c' : metadata.priority === 'normal' ? '#059669' : '#6b7280'};">${metadata.priority}</span></p>` : ''}
            </div>
        `;
    } else if (waypoint.type === 'parking') {
        const metadata = waypoint.metadata || {};
        cardHtml = `
            <div style="background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.3); max-width: 350px; border: 2px solid #FFA500;">
                <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #131320; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span>🅿️</span> Parking Location
                </h3>
                ${metadata.name ? `<p style="margin: 8px 0; color: #131320;"><strong>Name:</strong> ${metadata.name}</p>` : ''}
                ${metadata.address ? `<p style="margin: 8px 0; color: #131320;"><strong>Address:</strong> ${metadata.address}</p>` : ''}
                ${metadata.distance_to_delivery_km ? `<p style="margin: 8px 0; color: #131320;"><strong>Distance to Delivery:</strong> ${metadata.distance_to_delivery_km.toFixed(2)} km</p>` : ''}
            </div>
        `;
    } else if (waypoint.type === 'depot') {
        const metadata = waypoint.metadata || {};
        cardHtml = `
            <div style="background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.3); max-width: 350px; border: 2px solid #FF0000;">
                <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #131320; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span>🏭</span> Depot
                </h3>
                ${metadata.name ? `<p style="margin: 8px 0; color: #131320;"><strong>Name:</strong> ${metadata.name}</p>` : ''}
                ${metadata.address ? `<p style="margin: 8px 0; color: #131320;"><strong>Address:</strong> ${metadata.address}</p>` : ''}
            </div>
        `;
    }

    if (cardHtml) {
        const mapContainer = document.getElementById('route-map-container');
        if (mapContainer) {
            deliveryInfoCard = document.createElement('div');
            deliveryInfoCard.id = 'delivery-info-card';
            deliveryInfoCard.innerHTML = cardHtml;
            deliveryInfoCard.style.position = 'absolute';
            deliveryInfoCard.style.top = '10px';
            deliveryInfoCard.style.left = '10px';
            deliveryInfoCard.style.zIndex = '2000';
            mapContainer.appendChild(deliveryInfoCard);
        }
    }

    // Highlight the marker on the map (if it exists)
    // Find and highlight the corresponding marker
    currentRouteMarkers.forEach((marker, index) => {
        const markerLat = marker.getLatLng().lat;
        const markerLng = marker.getLatLng().lng;

        // Check if this marker matches the clicked waypoint (with small tolerance)
        if (Math.abs(markerLat - lat) < 0.0001 && Math.abs(markerLng - lng) < 0.0001) {
            // Open popup if available
            if (marker.getPopup()) {
                marker.openPopup();
            }
        }
    });
}

// Display a planned route on map (for routes that haven't been created yet)
async function displayPlannedRouteOnMap(route, color, index) {
    if (!routeMap) {
        setTimeout(() => displayPlannedRouteOnMap(route, color, index), 500);
        return;
    }

    if (!route.order_ids || route.order_ids.length === 0) {
        return;
    }

    // Load order locations
    const orders = [];
    for (const orderId of route.order_ids) {
        try {
            const order = await apiCall(`/orders/${orderId}`);
            if (order.latitude && order.longitude) {
                orders.push({
                    lat: order.latitude,
                    lng: order.longitude,
                    order_number: order.order_number,
                    delivery_address: order.delivery_address
                });
            }
        } catch (error) {
            console.error(`Failed to load order ${orderId}:`, error);
        }
    }

    if (orders.length === 0) {
        return;
    }

    // Get depot location
    const depots = await apiCall('/depots');
    const depot = depots[0];
    if (!depot || !depot.latitude || !depot.longitude) {
        return;
    }

    // Create waypoints (depot + orders)
    const waypoints = [
        { lat: depot.latitude, lng: depot.longitude, type: 'depot' },
        ...orders.map(o => ({ ...o, type: 'delivery' }))
    ];

    // Draw route connecting all waypoints
    const latlngs = waypoints.map(w => [w.lat, w.lng]);
    const routeLayer = L.polyline(latlngs, {
        color: color,
        weight: 5,
        opacity: 0.7
    }).addTo(routeMap);
    currentRouteLayers.push(routeLayer);

    // Add markers for waypoints
    waypoints.forEach((waypoint, idx) => {
        const iconColor = waypoint.type === 'depot' ? '#FF0000' : color;
        const iconHtml = waypoint.type === 'depot' ? '🏭' : '📦';
        const icon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="background-color: ${iconColor}; border: 3px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.4);">${iconHtml}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        const marker = L.marker([waypoint.lat, waypoint.lng], { icon }).addTo(routeMap);
        marker.bindPopup(`<strong>${waypoint.type.toUpperCase()}</strong><br>${waypoint.order_number || 'Depot'}`);
        currentRouteMarkers.push(marker);
        currentRouteLayers.push(marker);
    });
}

// ==================== SUMMARY PAGE FUNCTIONS ====================

let summaryCharts = {};

async function loadSummary() {
    try {
        const [orders, routes, drivers] = await Promise.all([
            apiCall('/orders'),
            apiCall('/routes'),
            apiCall('/drivers')
        ]);

        // Calculate metrics
        const totalOrders = orders.length;
        const completedOrders = orders.filter(o => o.status === 'completed').length;
        const activeRoutes = routes.filter(r => r.status === 'in_transit' || r.status === 'planned').length;
        const activeDrivers = drivers.filter(d => d.status === 'on_route').length;

        // Calculate average delivery time (mock for now - would need actual delivery times)
        const completedWithTime = orders.filter(o => o.status === 'completed' && o.delivered_at);
        const avgTime = completedWithTime.length > 0 ? '2.5h' : '-';

        // Calculate success rate
        const successRate = totalOrders > 0 ? ((completedOrders / totalOrders) * 100).toFixed(1) + '%' : '0%';

        // Update metric cards
        document.getElementById('metric-total-orders').textContent = totalOrders;
        document.getElementById('metric-completed').textContent = completedOrders;
        document.getElementById('metric-active-routes').textContent = activeRoutes;
        document.getElementById('metric-active-drivers').textContent = activeDrivers;
        document.getElementById('metric-avg-time').textContent = avgTime;
        document.getElementById('metric-success-rate').textContent = successRate;

        // Update charts
        updateStatusChart(orders);
        updateSourceChart(orders);
        updateTrendChart(orders);
        updatePriorityChart(orders);

        // Update recent activity
        updateRecentActivity(orders);
    } catch (error) {
        console.error('Failed to load summary:', error);
    }
}

function updateStatusChart(orders) {
    const ctx = document.getElementById('status-chart-canvas');
    if (!ctx) return;

    const statusCounts = {
        pending: 0,
        assigned: 0,
        in_transit: 0,
        completed: 0,
        failed: 0
    };

    orders.forEach(order => {
        const status = order.status || 'pending';
        if (statusCounts.hasOwnProperty(status)) {
            statusCounts[status]++;
        }
    });

    if (summaryCharts.status) {
        summaryCharts.status.destroy();
    }

    summaryCharts.status = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(statusCounts).map(s => s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')),
            datasets: [{
                data: Object.values(statusCounts),
                backgroundColor: [
                    '#3b82f6',
                    '#8b5cf6',
                    '#f59e0b',
                    '#10b981',
                    '#ef4444'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#b0b8c4',
                        padding: 15
                    }
                }
            }
        }
    });
}

function updateSourceChart(orders) {
    const ctx = document.getElementById('source-chart-canvas');
    if (!ctx) return;

    const sourceCounts = {};
    orders.forEach(order => {
        const source = order.source || 'unknown';
        sourceCounts[source] = (sourceCounts[source] || 0) + 1;
    });

    if (summaryCharts.source) {
        summaryCharts.source.destroy();
    }

    summaryCharts.source = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(sourceCounts).map(s => s.charAt(0).toUpperCase() + s.slice(1)),
            datasets: [{
                label: 'Orders',
                data: Object.values(sourceCounts),
                backgroundColor: '#2d89be',
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#b0b8c4'
                    },
                    grid: {
                        color: '#1e293b'
                    }
                },
                x: {
                    ticks: {
                        color: '#b0b8c4'
                    },
                    grid: {
                        color: '#1e293b'
                    }
                }
            }
        }
    });
}

function updateTrendChart(orders) {
    const ctx = document.getElementById('trend-chart-canvas');
    if (!ctx) return;

    // Group orders by date
    const dateCounts = {};
    orders.forEach(order => {
        if (order.created_at) {
            const date = new Date(order.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            dateCounts[date] = (dateCounts[date] || 0) + 1;
        }
    });

    const sortedDates = Object.keys(dateCounts).sort((a, b) => {
        return new Date(a) - new Date(b);
    }).slice(-7); // Last 7 days

    if (summaryCharts.trend) {
        summaryCharts.trend.destroy();
    }

    summaryCharts.trend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sortedDates,
            datasets: [{
                label: 'Orders',
                data: sortedDates.map(d => dateCounts[d] || 0),
                borderColor: '#2d89be',
                backgroundColor: 'rgba(45, 137, 190, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#b0b8c4'
                    },
                    grid: {
                        color: '#1e293b'
                    }
                },
                x: {
                    ticks: {
                        color: '#b0b8c4'
                    },
                    grid: {
                        color: '#1e293b'
                    }
                }
            }
        }
    });
}

function updatePriorityChart(orders) {
    const ctx = document.getElementById('priority-chart-canvas');
    if (!ctx) return;

    const priorityCounts = {
        urgent: 0,
        high: 0,
        normal: 0,
        low: 0
    };

    orders.forEach(order => {
        const priority = order.priority || 'normal';
        if (priorityCounts.hasOwnProperty(priority)) {
            priorityCounts[priority]++;
        }
    });

    if (summaryCharts.priority) {
        summaryCharts.priority.destroy();
    }

    summaryCharts.priority = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: Object.keys(priorityCounts).map(p => p.charAt(0).toUpperCase() + p.slice(1)),
            datasets: [{
                data: Object.values(priorityCounts),
                backgroundColor: [
                    '#ef4444',
                    '#f59e0b',
                    '#3b82f6',
                    '#10b981'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#b0b8c4',
                        padding: 15
                    }
                }
            }
        }
    });
}

function updateRecentActivity(orders) {
    const container = document.getElementById('recent-activity-list');
    if (!container) return;

    // Get recent orders sorted by updated_at
    const recentOrders = [...orders]
        .sort((a, b) => {
            const dateA = new Date(a.updated_at || a.created_at);
            const dateB = new Date(b.updated_at || b.created_at);
            return dateB - dateA;
        })
        .slice(0, 10);

    if (recentOrders.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No recent activity</p>';
        return;
    }

    container.innerHTML = recentOrders.map(order => {
        const status = order.status || 'pending';
        const icon = status === 'completed' ? '✅' : status === 'in_transit' ? '🚚' : status === 'assigned' ? '📋' : '📦';
        const time = new Date(order.updated_at || order.created_at).toLocaleString();

        return `
            <div class="activity-item">
                <div class="activity-icon">${icon}</div>
                <div class="activity-content">
                    <div class="activity-title">${order.order_number || `Order #${order.id}`} - ${order.delivery_address || 'No address'}</div>
                    <div class="activity-time">${time}</div>
                </div>
            </div>
        `;
    }).join('');
}

function refreshSummary() {
    loadSummary();
}

// Make function globally accessible
if (typeof window !== 'undefined') {
    window.refreshSummary = refreshSummary;
}

// ==================== ARCHIVE PAGE FUNCTIONS ====================

async function loadArchive() {
    try {
        const statusFilter = document.getElementById('archive-filter-status')?.value || '';
        const dateFilter = document.getElementById('archive-filter-date')?.value || '';

        // Get all orders and filter for completed/failed
        const allOrders = await apiCall('/orders');
        let orders = allOrders.filter(o => {
            const status = o.status || '';
            return status === 'completed' || status === 'failed';
        });

        // Apply status filter if provided
        if (statusFilter) {
            orders = orders.filter(o => (o.status || '') === statusFilter);
        }

        // Filter by date if provided
        let filteredOrders = orders;
        if (dateFilter) {
            const filterDate = new Date(dateFilter);
            filteredOrders = orders.filter(order => {
                if (!order.delivered_at && !order.updated_at) return false;
                const orderDate = new Date(order.delivered_at || order.updated_at);
                return orderDate.toDateString() === filterDate.toDateString();
            });
        }

        // Sort by delivered_at or updated_at descending
        filteredOrders.sort((a, b) => {
            const dateA = new Date(a.delivered_at || a.updated_at || 0);
            const dateB = new Date(b.delivered_at || b.updated_at || 0);
            return dateB - dateA;
        });

        // Calculate statistics
        const now = new Date();
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

        const thisWeek = filteredOrders.filter(o => {
            const date = new Date(o.delivered_at || o.updated_at);
            return date >= weekAgo;
        }).length;

        const thisMonth = filteredOrders.filter(o => {
            const date = new Date(o.delivered_at || o.updated_at);
            return date >= monthAgo;
        }).length;

        // Update statistics
        document.getElementById('archive-total').textContent = filteredOrders.length;
        document.getElementById('archive-month').textContent = thisMonth;
        document.getElementById('archive-week').textContent = thisWeek;

        // Display archive items
        displayArchiveItems(filteredOrders);
    } catch (error) {
        console.error('Failed to load archive:', error);
    }
}

function displayArchiveItems(orders) {
    const container = document.getElementById('archive-list');
    if (!container) return;

    if (orders.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">No archived deliveries found</div>';
        return;
    }

    container.innerHTML = orders.map(order => {
        const status = order.status || 'completed';
        const statusClass = status === 'completed' ? 'completed' : 'failed';
        const deliveredDate = order.delivered_at ? new Date(order.delivered_at).toLocaleString() : 'N/A';
        const createdDate = order.created_at ? new Date(order.created_at).toLocaleString() : 'N/A';

        // Calculate delivery time if both dates exist
        let deliveryTime = 'N/A';
        if (order.created_at && order.delivered_at) {
            const created = new Date(order.created_at);
            const delivered = new Date(order.delivered_at);
            const diffHours = Math.round((delivered - created) / (1000 * 60 * 60));
            deliveryTime = `${diffHours}h`;
        }

        return `
            <div class="archive-item">
                <div class="archive-item-header">
                    <div>
                        <div class="archive-item-title">${order.order_number || `Order #${order.id}`}</div>
                        <div class="archive-item-meta">
                            <span class="archive-meta-item">📍 ${order.delivery_address || 'No address'}</span>
                            <span class="archive-meta-item">👤 ${order.customer_name || 'No name'}</span>
                            <span class="archive-meta-item">📞 ${order.customer_phone || 'No phone'}</span>
                        </div>
                    </div>
                    <span class="archive-status-badge ${statusClass}">${status}</span>
                </div>
                <div class="archive-item-details">
                    <div class="archive-detail-group">
                        <span class="archive-detail-label">Delivered At</span>
                        <span class="archive-detail-value">${deliveredDate}</span>
                    </div>
                    <div class="archive-detail-group">
                        <span class="archive-detail-label">Created At</span>
                        <span class="archive-detail-value">${createdDate}</span>
                    </div>
                    <div class="archive-detail-group">
                        <span class="archive-detail-label">Delivery Time</span>
                        <span class="archive-detail-value">${deliveryTime}</span>
                    </div>
                    <div class="archive-detail-group">
                        <span class="archive-detail-label">Source</span>
                        <span class="archive-detail-value">${order.source || 'N/A'}</span>
                    </div>
                    ${order.driver_notes ? `
                    <div class="archive-detail-group" style="grid-column: 1 / -1;">
                        <span class="archive-detail-label">Driver Notes</span>
                        <span class="archive-detail-value">${order.driver_notes}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// Make function globally accessible
if (typeof window !== 'undefined') {
    window.loadArchive = loadArchive;
}
