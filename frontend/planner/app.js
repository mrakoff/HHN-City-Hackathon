const API_BASE = 'http://localhost:8000/api';

let routeMap = null;
let currentRouteMarkers = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupKeyboardShortcuts();
    loadOrders();
    loadDrivers();
    loadRoutes();
    loadDepots();
    loadParkingLocations();
    initRouteMap();
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
async function loadOrders() {
    const status = document.getElementById('order-status-filter')?.value || '';
    const source = document.getElementById('order-source-filter')?.value || '';

    let url = '/orders';
    const params = [];
    if (status) params.push(`status=${status}`);
    if (source) params.push(`source=${source}`);
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

    container.innerHTML = orders.map(order => `
        <div class="order-card ${order.status}">
            <h3>${order.order_number || `Order #${order.id}`}</h3>
            <p><strong>Address:</strong> ${order.delivery_address}</p>
            ${order.customer_name ? `<p><strong>Customer:</strong> ${order.customer_name}</p>` : ''}
            ${order.customer_phone ? `<p><strong>Phone:</strong> ${order.customer_phone}</p>` : ''}
            <p><strong>Status:</strong> <span class="badge ${order.status}">${order.status}</span></p>
            ${order.source ? `<p><strong>Source:</strong> ${order.source}</p>` : ''}
            ${order.validation_errors && order.validation_errors.length > 0 ?
                `<p style="color: red;"><strong>Errors:</strong> ${order.validation_errors.join(', ')}</p>` : ''}
            <div style="margin-top: 10px;">
                <button class="btn btn-secondary" onclick="editOrder(${order.id})">Edit</button>
                <button class="btn btn-danger" onclick="deleteOrder(${order.id})">Delete</button>
            </div>
        </div>
    `).join('');
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
                <label>Priority</label>
                <select name="priority">
                    <option value="normal">Normal</option>
                    <option value="low">Low</option>
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

    try {
        const uploadForm = new FormData();
        uploadForm.append('file', file);
        uploadForm.append('source', source);

        const response = await fetch(`${API_BASE}/orders/upload`, {
            method: 'POST',
            body: uploadForm
        });

        if (!response.ok) throw new Error('Upload failed');

        const order = await response.json();
        closeModal();
        loadOrders();
        if (order.validation_errors && order.validation_errors.length > 0) {
            alert(`Order parsed but has validation errors: ${order.validation_errors.join(', ')}`);
        }
    } catch (error) {
        alert(`Upload failed: ${error.message}`);
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
        container.innerHTML = '<p>No routes found</p>';
        return;
    }

    container.innerHTML = routes.map(route => `
        <div class="route-card">
            <h3>Route #${route.id} - ${route.name || 'Unnamed'}</h3>
            <p><strong>Status:</strong> ${route.status}</p>
            <div style="margin-top: 10px;">
                <button class="btn btn-primary" onclick="viewRoute(${route.id})">View Route</button>
                <button class="btn btn-secondary" onclick="optimizeRoute(${route.id})">Optimize</button>
                <button class="btn btn-danger" onclick="deleteRoute(${route.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

function showCreateRouteModal() {
    // Simplified - would need to load drivers and orders
    showModal(`
        <h2>Create New Route</h2>
        <p>Route creation form would go here</p>
        <div class="form-actions">
            <button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button>
        </div>
    `);
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
        const route = await apiCall(`/routes/${routeId}`);
        displayRouteOnMap(route);
    } catch (error) {
        console.error('Failed to load route:', error);
    }
}

function displayRouteOnMap(route) {
    if (!routeMap) return;

    // Clear existing markers
    currentRouteMarkers.forEach(m => routeMap.removeLayer(m));
    currentRouteMarkers = [];

    // Add markers for route orders
    if (route.route_orders) {
        route.route_orders.forEach((ro, index) => {
            if (ro.order && ro.order.latitude && ro.order.longitude) {
                const marker = L.marker([ro.order.latitude, ro.order.longitude])
                    .addTo(routeMap)
                    .bindPopup(`Stop ${index + 1}: ${ro.order.delivery_address}`);
                currentRouteMarkers.push(marker);
            }
        });
    }

    // Fit map to show all markers
    if (currentRouteMarkers.length > 0) {
        const group = new L.featureGroup(currentRouteMarkers);
        routeMap.fitBounds(group.getBounds().pad(0.1));
    }
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
    routeMap = L.map('route-map').setView([51.505, -0.09], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(routeMap);
}

// Modal
function showModal(content) {
    document.getElementById('modal-body').innerHTML = content;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}
