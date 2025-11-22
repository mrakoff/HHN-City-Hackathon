const API_BASE = 'http://localhost:8000/api';

let routeMap = null;
let currentRouteMarkers = [];
let currentRouteLayers = []; // Track all route-related layers (markers, polylines, arrows)

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupKeyboardShortcuts();
    loadOrders();
    loadDrivers();
    loadRoutes();
    loadDepots();
    loadParkingLocations();
    // Don't initialize map immediately - wait for routes tab to be shown
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

            // Initialize map when routes tab is shown
            if (tab === 'routes' && !routeMap) {
                setTimeout(() => {
                    initRouteMap();
                    console.log('Map initialized for routes tab');
                }, 200); // Small delay to ensure container is visible
            } else if (tab === 'routes' && routeMap) {
                // Invalidate size when switching back to routes tab
                setTimeout(() => {
                    routeMap.invalidateSize();
                    console.log('Map size invalidated');
                }, 200);
            }
        });
    });
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
            throw new Error(`API error: ${response.statusText}`);
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
    currentOrderView = view;
    // Update tab buttons
    document.querySelectorAll('.order-tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        }
    });
    loadOrders();
}

async function loadOrders() {
    const status = document.getElementById('order-status-filter')?.value || '';
    const source = document.getElementById('order-source-filter')?.value || '';

    let url = '/orders';
    const params = [];
    if (status) params.push(`status=${status}`);
    if (source) params.push(`source=${source}`);
    if (currentOrderView === 'unfinished') {
        params.push('unfinished=true');
    }
    // Don't add unfinished=false - that would filter out unfinished orders
    if (params.length) url += '?' + params.join('&');

    try {
        const orders = await apiCall(url);
        displayOrders(orders);
    } catch (error) {
        console.error('Failed to load orders:', error);
    }
}

function displayOrders(orders) {
    const container = document.getElementById('orders-list');
    if (!orders || orders.length === 0) {
        container.innerHTML = '<p>No orders found</p>';
        return;
    }

    container.innerHTML = orders.map(order => {
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
        await apiCall(`/routes/${routeId}/optimize`, { method: 'POST' });
        alert('Route optimized successfully!');
        loadRoutes();
    } catch (error) {
        alert(`Optimization failed: ${error.message}`);
    }
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
        displayRouteOnMap(routeData);
    } catch (error) {
        console.error('Failed to load route:', error);
        alert(`Failed to load route visualization: ${error.message}`);
    }
}

function displayRouteOnMap(routeData) {
    console.log('Displaying route on map:', routeData);

    if (!routeMap) {
        // Initialize map if not already done
        console.log('Map not initialized, initializing now...');
        initRouteMap();
        // Wait a bit for map to initialize
        setTimeout(() => {
            console.log('Retrying display after map init');
            displayRouteOnMap(routeData);
        }, 500);
        return;
    }

    // Double-check map is ready
    if (!routeMap || !routeMap.getContainer()) {
        console.error('Map container not ready');
        setTimeout(() => displayRouteOnMap(routeData), 300);
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
            html: `<div style="background-color: ${color}; border: 3px solid white; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">${iconHtml}</div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
    };

    // Add waypoints with color-coded markers
    const waypointMarkers = [];
    routeData.waypoints.forEach((waypoint, index) => {
        const icon = createIcon(waypoint.color, waypoint.type);
        const marker = L.marker([waypoint.lat, waypoint.lng], { icon })
            .addTo(routeMap);

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
    if (routeData.geometry) {
        console.log('Using OSRM geometry for route display');
        // Use OSRM route geometry (GeoJSON LineString) - this shows actual roads!
        try {
            const routeLayer = L.geoJSON(routeData.geometry, {
                style: {
                    color: '#0066cc',
                    weight: 5,
                    opacity: 0.8
                }
            }).addTo(routeMap);
            currentRouteLayers.push(routeLayer);

            // Add direction arrows along the route
            const coordinates = routeData.geometry.coordinates;
            if (coordinates && coordinates.length > 1) {
                // Add arrows at regular intervals
                const arrowInterval = Math.max(1, Math.floor(coordinates.length / 10));
                for (let i = arrowInterval; i < coordinates.length - 1; i += arrowInterval) {
                    const [lng1, lat1] = coordinates[i - 1];
                    const [lng2, lat2] = coordinates[i];
                    const midLat = (lat1 + lat2) / 2;
                    const midLng = (lng1 + lng2) / 2;

                    const bearing = getBearing({ lat: lat1, lng: lng1 }, { lat: lat2, lng: lng2 });
                    const arrowIcon = L.divIcon({
                        className: 'route-arrow',
                        html: `<div style="color: #0066cc; font-size: 18px; transform: rotate(${bearing}deg);">➤</div>`,
                        iconSize: [18, 18],
                        iconAnchor: [9, 9]
                    });

                    const arrowMarker = L.marker([midLat, midLng], { icon: arrowIcon, interactive: false })
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
    if (!routeData.geometry && routeData.segments && routeData.segments.length > 0) {
        console.log('Using fallback segments (no OSRM geometry available)');
        routeData.segments.forEach((segment, index) => {
            const fromWaypoint = routeData.waypoints[index];
            const toWaypoint = routeData.waypoints[index + 1];

            // Determine segment color based on destination type
            const segmentColor = toWaypoint.color;
            const segmentWeight = 4;

            const polyline = L.polyline(
                [
                    [segment.from.lat, segment.from.lng],
                    [segment.to.lat, segment.to.lng]
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
            const midLng = (segment.from.lng + segment.to.lng) / 2;

            // Create arrow marker
            const arrowIcon = L.divIcon({
                className: 'route-arrow',
                html: `<div style="color: ${segmentColor}; font-size: 20px; transform: rotate(${getBearing(segment.from, segment.to)}deg);">➤</div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });

            const arrowMarker = L.marker([midLat, midLng], { icon: arrowIcon, interactive: false })
                .addTo(routeMap);
            currentRouteLayers.push(arrowMarker);
        });
    } else if (!routeData.geometry) {
        // Final fallback: draw simple polyline connecting all waypoints
        const latlngs = routeData.waypoints.map(w => [w.lat, w.lng]);
        const fallbackPolyline = L.polyline(latlngs, {
            color: '#0066cc',
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

    // Display route summary
    const summary = routeData.summary;
    const summaryHtml = `
        <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); max-width: 250px;">
            <h3 style="margin: 0 0 10px 0; font-size: 16px;">Route Summary</h3>
            <p style="margin: 5px 0;"><strong>Distance:</strong> ${summary.total_distance_km.toFixed(2)} km</p>
            <p style="margin: 5px 0;"><strong>Time:</strong> ${Math.round(summary.total_time_minutes)} min</p>
            <p style="margin: 5px 0;"><strong>Stops:</strong> ${summary.waypoint_count}</p>
            <p style="margin: 5px 0;"><strong>Deliveries:</strong> ${summary.delivery_count}</p>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
                <p style="margin: 5px 0; font-size: 12px;"><strong>Legend:</strong></p>
                <p style="margin: 2px 0; font-size: 12px;"><span style="color: ${routeData.colors.depot};">●</span> Depot</p>
                <p style="margin: 2px 0; font-size: 12px;"><span style="color: ${routeData.colors.parking};">●</span> Parking</p>
                <p style="margin: 2px 0; font-size: 12px;"><span style="color: ${routeData.colors.delivery};">●</span> Delivery</p>
            </div>
        </div>
    `;

    // Remove existing summary if any
    const existingSummary = document.getElementById('route-summary');
    if (existingSummary) {
        existingSummary.remove();
    }

    // Add summary to map container
    const mapContainerDiv = document.getElementById('route-map-container');
    if (mapContainerDiv) {
        const summaryDiv = document.createElement('div');
        summaryDiv.id = 'route-summary';
        summaryDiv.innerHTML = summaryHtml;
        mapContainerDiv.appendChild(summaryDiv);
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

    // Set initial view to Berlin (where sample data is)
    routeMap = L.map('route-map', {
        preferCanvas: false, // Use canvas for better performance
        zoomControl: true
    }).setView([52.5200, 13.4050], 12);

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
