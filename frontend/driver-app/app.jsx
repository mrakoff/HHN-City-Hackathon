const { useState, useEffect, useMemo, useCallback, useRef } = React;
const http = window.SharedApi;

const STATUS_OPTIONS = [
  { value: "assigned", label: "Assigned / Ready" },
  { value: "accepted", label: "Accepted" },
  { value: "en_route", label: "On the way" },
  { value: "arrived", label: "Arrived on site" },
  { value: "delivered", label: "Delivered" },
  { value: "failed", label: "Issue / Failed" },
];

const STATUS_LABELS = {
  assigned: "Assigned",
  accepted: "Accepted",
  en_route: "On the way",
  arrived: "Arrived",
  delivered: "Delivered",
  failed: "Issue",
  unassigned: "Unassigned",
};

const formatRelativeTime = (value) => {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleString();
};

const StatusBadge = ({ status }) => {
  if (!status) return null;
  const normalized = status.toLowerCase();
  return <span className={`status-badge ${normalized}`}>{STATUS_LABELS[normalized] || normalized}</span>;
};

const useGeolocation = () => {
  const [coords, setCoords] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const capture = useCallback(() => {
    if (!navigator.geolocation) {
      setError("GPS not supported on this device.");
      return;
    }
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          lat: Number(position.coords.latitude.toFixed(6)),
          lng: Number(position.coords.longitude.toFixed(6)),
        });
        setError(null);
        setLoading(false);
      },
      (err) => {
        setError(err.message || "Unable to fetch GPS location");
        setLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }, []);

  const reset = useCallback(() => {
    setCoords(null);
    setError(null);
  }, []);

  return { coords, capture, loading, error, reset };
};

// Route Plan Overview Component
const RoutePlanOverview = ({ orders, selectedOrderId, onSelect, onQuickStatusUpdate, driverId, routeWaypoints = [] }) => {
  if (!orders.length) {
    return <div className="empty-state">No active stops yet. Pull to refresh after routes are assigned.</div>;
  }

  // Separate orders with and without route sequence
  const sequencedOrders = orders
    .filter(a => a.route_sequence != null)
    .sort((a, b) => a.route_sequence - b.route_sequence);
  const unsequencedOrders = orders.filter(a => a.route_sequence == null);

  // Build a map of order IDs to assignments for quick lookup
  const orderMap = new Map();
  sequencedOrders.forEach(assignment => {
    orderMap.set(assignment.order.id, assignment);
  });

  // Create a combined list of waypoints (deliveries + parking spots) in sequence
  // If we have route waypoints, use them; otherwise just show orders
  let combinedWaypoints = [];

  if (routeWaypoints.length > 0) {
    // Build a map of order IDs to assignments for matching
    const orderIdMap = new Map();
    sequencedOrders.forEach(assignment => {
      orderIdMap.set(assignment.order.id, assignment);
      if (assignment.order.order_number) {
        orderIdMap.set(assignment.order.order_number, assignment);
      }
    });

    // Sort all waypoints by sequence
    const sortedWaypoints = [...routeWaypoints].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));

    sortedWaypoints.forEach(wp => {
      if (wp.type === "depot") {
        combinedWaypoints.push({ type: "depot", waypoint: wp, sequence: wp.sequence || 0 });
      } else if (wp.type === "parking") {
        combinedWaypoints.push({ type: "parking", waypoint: wp, sequence: wp.sequence || 0 });
      } else if (wp.type === "delivery" && wp.metadata) {
        // Try to find matching assignment by order ID or order_number
        const orderId = wp.metadata.id;
        const orderNumber = wp.metadata.order_number;
        const assignment = orderIdMap.get(orderId) || (orderNumber ? orderIdMap.get(orderNumber) : null);

        if (assignment) {
          combinedWaypoints.push({
            type: "delivery",
            assignment: assignment,
            waypoint: wp,
            sequence: wp.sequence || 0
          });
        }
      }
    });
  } else {
    // Fallback: just show orders without parking spots
    combinedWaypoints = sequencedOrders.map(assignment => ({
      type: "delivery",
      assignment: assignment,
      waypoint: null,
      sequence: assignment.route_sequence
    }));
  }

  const handleQuickStatus = async (orderId, newStatus) => {
    try {
      const url = driverId
        ? `/orders/driver/orders/${orderId}/status?driver_id=${driverId}`
        : `/orders/driver/orders/${orderId}/status`;
      await http.postJSON(url, { status: newStatus });
      onQuickStatusUpdate();
    } catch (err) {
      console.error("Failed to update status:", err);
      alert("Failed to update status: " + err.message);
    }
  };

  return (
    <div>
      {sequencedOrders.length > 0 && (
        <div className="route-plan-section">
          <h3 style={{ marginTop: 0, marginBottom: "16px", fontSize: "1.2rem", color: "var(--accent-primary)" }}>
            📋 Route Plan ({sequencedOrders.length} stops)
          </h3>
          <div className="route-stops-list">
            {combinedWaypoints.map((item, index) => {
              if (item.type === "parking") {
                const { waypoint } = item;
                const parkingAddress = waypoint.metadata?.address || waypoint.metadata?.name || "Parking Spot";
                const googleMapsUrl = `https://www.google.com/maps?q=${waypoint.lat},${waypoint.lng}`;

                return (
                  <div
                    key={`parking-${waypoint.id || index}`}
                    className="route-stop-card parking-spot"
                  >
                    <div className="stop-number parking-icon">
                      🅿️
                    </div>
                    <div className="stop-content">
                      <div className="stop-header">
                        <div>
                          <strong>Parking Spot</strong>
                          <div className="stop-address">{parkingAddress}</div>
                        </div>
                      </div>
                      <button
                        className="btn-quick btn-quick-info"
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(googleMapsUrl, "_blank");
                        }}
                      >
                        📍 View Location
                      </button>
                    </div>
                  </div>
                );
              } else if (item.type === "delivery" && item.assignment) {
                const { assignment, waypoint } = item;
                const { order } = assignment;
                const status = (order.driver_status || order.status || "").toLowerCase();
                const isCompleted = status === "delivered";
                const isFailed = status === "failed";
                const isActive = order.id === selectedOrderId;

                return (
                  <div
                    key={order.id}
                    className={`route-stop-card ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""} ${isFailed ? "failed" : ""}`}
                    onClick={() => onSelect(order.id)}
                  >
                    <div className="stop-number">
                      {assignment.route_sequence}
                    </div>
                    <div className="stop-content">
                      <div className="stop-header">
                        <div>
                          <strong>{order.order_number || `Order #${order.id}`}</strong>
                          <div className="stop-address">{order.delivery_address}</div>
                        </div>
                        <StatusBadge status={
                          order.driver_status ||
                          (assignment.route_sequence ? "assigned" : order.status) ||
                          "assigned"
                        } />
                      </div>
                      {!isCompleted && !isFailed && (
                        <div className="quick-actions">
                          <button
                            className="btn-quick btn-quick-success"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleQuickStatus(order.id, "delivered");
                            }}
                          >
                            ✓ Delivered
                          </button>
                          <button
                            className="btn-quick btn-quick-warning"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleQuickStatus(order.id, "failed");
                            }}
                          >
                            ⚠ Issue
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              } else if (item.type === "depot") {
                const { waypoint } = item;
                const depotName = waypoint.metadata?.name || "Depot";

                return (
                  <div
                    key={`depot-${waypoint.id || 0}`}
                    className="route-stop-card depot"
                  >
                    <div className="stop-number depot-icon">
                      🏭
                    </div>
                    <div className="stop-content">
                      <div className="stop-header">
                        <div>
                          <strong>{depotName}</strong>
                          <div className="stop-address">Starting Point</div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }
              return null;
            })}
          </div>
        </div>
      )}

      {unsequencedOrders.length > 0 && (
        <div style={{ marginTop: "24px" }}>
          <h4 style={{ marginBottom: "12px", fontSize: "0.95rem", color: "var(--text-secondary)" }}>
            Additional Orders ({unsequencedOrders.length})
          </h4>
          {unsequencedOrders.map((assignment) => {
            const { order } = assignment;
            const active = order.id === selectedOrderId;
            return (
              <div
                key={order.id}
                className={`order-card ${active ? "active" : ""}`}
                onClick={() => onSelect(order.id)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h4>{order.order_number || `Order #${order.id}`}</h4>
                  <StatusBadge status={
                    order.driver_status ||
                    (assignment.route_sequence ? "assigned" : order.status) ||
                    "assigned"
                  } />
                </div>
                <div className="meta">{order.delivery_address}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Order Detail Component (Simplified - No Map)
const OrderDetail = ({ assignment, driverId, onRefresh, onBack, showBackButton = false }) => {
  const order = assignment.order;
  const [photoFile, setPhotoFile] = useState(null);
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState(order.driver_status || "accepted");
  const [failureReason, setFailureReason] = useState(order.failure_reason || "");
  const [uploading, setUploading] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);
  const canvasRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const geo = useGeolocation();

  useEffect(() => {
    setStatus(order.driver_status || "accepted");
    setNotes("");
    setFailureReason(order.failure_reason || "");
    setPhotoFile(null);
    setFeedback(null);
    setError(null);
    clearCanvas();
    geo.reset();
  }, [order.id]);

  const getPoint = (event) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const source = event.touches ? event.touches[0] : event;
    return {
      x: source.clientX - rect.left,
      y: source.clientY - rect.top,
    };
  };

  const startDrawing = (event) => {
    setDrawing(true);
    const ctx = canvasRef.current.getContext("2d");
    const { x, y } = getPoint(event);
    ctx.beginPath();
    ctx.moveTo(x, y);
    event.preventDefault();
  };

  const draw = (event) => {
    if (!drawing) return;
    const ctx = canvasRef.current.getContext("2d");
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#111827";
    const { x, y } = getPoint(event);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
    setHasSignature(true);
    event.preventDefault();
  };

  const stopDrawing = () => {
    setDrawing(false);
  };

  const clearCanvas = () => {
    if (!canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    setHasSignature(false);
  };

  const handleStatusUpdate = async (event) => {
    event.preventDefault();
    setSavingStatus(true);
    setError(null);
    setFeedback(null);

    try {
      const url = driverId
        ? `/orders/driver/orders/${order.id}/status?driver_id=${driverId}`
        : `/orders/driver/orders/${order.id}/status`;
      await http.postJSON(url, {
        status,
        notes: notes || undefined,
        failure_reason: status === "failed" ? failureReason || "Issue reported by driver" : undefined,
        gps_lat: geo.coords ? geo.coords.lat : undefined,
        gps_lng: geo.coords ? geo.coords.lng : undefined,
      });
      setFeedback("Status updated successfully");
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingStatus(false);
    }
  };

  const handleProofUpload = async (event) => {
    event.preventDefault();
    setFeedback(null);
    setError(null);

    if (!photoFile && !hasSignature) {
      setError("Please attach a photo or capture a signature.");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    if (photoFile) {
      formData.append("photo", photoFile);
    }
    if (hasSignature && canvasRef.current) {
      formData.append("signature_data", canvasRef.current.toDataURL("image/png"));
    }
    if (notes) formData.append("notes", notes);
    if (geo.coords) {
      formData.append("gps_lat", geo.coords.lat);
      formData.append("gps_lng", geo.coords.lng);
    }
    if (driverId) {
      formData.append("driver_id", driverId);
    }

    try {
      await http.upload(`/orders/driver/orders/${order.id}/proof`, formData);
      setFeedback("Proof uploaded successfully");
      setPhotoFile(null);
      setNotes("");
      clearCanvas();
      geo.reset();
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="order-detail">
      {showBackButton && onBack && (
        <div style={{ marginBottom: "16px" }}>
          <button
            className="btn-secondary"
            onClick={onBack}
            style={{ display: "flex", alignItems: "center", gap: "8px" }}
          >
            ← Back to Orders
          </button>
        </div>
      )}
      <div className="section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h2>{order.customer_name || order.delivery_address}</h2>
            <p className="meta">{order.order_number ? `Order ${order.order_number}` : `Order #${order.id}`}</p>
            {assignment.route_sequence && (
              <p className="meta">Stop #{assignment.route_sequence}</p>
            )}
          </div>
          <StatusBadge status={
            order.driver_status ||
            (assignment.route_sequence ? "assigned" : order.status) ||
            "assigned"
          } />
        </div>
      </div>

      <div className="info-grid">
        <div className="info-card">
          <span>Delivery address</span>
          <strong>{order.delivery_address}</strong>
        </div>
        {order.customer_phone && (
          <div className="info-card">
            <span>Contact phone</span>
            <strong>
              {order.customer_phone}
              <a href={`tel:${order.customer_phone}`} style={{ marginLeft: "8px", fontSize: "0.8rem" }}>Call</a>
            </strong>
          </div>
        )}
      </div>

      {order.description && (
        <div className="section">
          <h3>Special instructions</h3>
          <p>{order.description}</p>
        </div>
      )}

      {/* Status Update Form */}
      <div className="section">
        <h3>Update Status</h3>
        {feedback && <div className="alert success">{feedback}</div>}
        {error && <div className="alert error">{error}</div>}
        <form onSubmit={handleStatusUpdate}>
          <div className="form-control">
            <label htmlFor="status-select">Current status</label>
            <select
              id="status-select"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-control">
            <label htmlFor="status-notes">Notes</label>
            <textarea
              id="status-notes"
              rows="3"
              placeholder="Add notes for dispatch..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {status === "failed" && (
            <div className="form-control">
              <label htmlFor="failure-reason">What went wrong?</label>
              <textarea
                id="failure-reason"
                rows="2"
                required
                placeholder="Customer unavailable, wrong address, etc."
                value={failureReason}
                onChange={(e) => setFailureReason(e.target.value)}
              />
            </div>
          )}

          <div className="button-row" style={{ alignItems: "center" }}>
            <button type="submit" className="btn-primary" disabled={savingStatus}>
              {savingStatus ? "Saving…" : "Update Status"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={geo.capture}
              disabled={geo.loading}
            >
              {geo.loading ? "Capturing GPS…" : "Use current GPS"}
            </button>
            {geo.coords && (
              <small>📍 {geo.coords.lat}, {geo.coords.lng}</small>
            )}
          </div>
          {geo.error && <small className="alert error">{geo.error}</small>}
        </form>
      </div>

      {/* Proof of Delivery */}
      <div className="section">
        <h3>Proof of Delivery</h3>
        {feedback && <div className="alert success">{feedback}</div>}
        {error && <div className="alert error">{error}</div>}

        <form onSubmit={handleProofUpload}>
          <div className="form-control">
            <label htmlFor="photo-input">Photo evidence</label>
            <input
              id="photo-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => setPhotoFile((e.target.files && e.target.files[0]) || null)}
            />
            {photoFile && <small>Selected: {photoFile.name}</small>}
          </div>

          <div className="form-control">
            <label>Recipient signature</label>
            <canvas
              ref={canvasRef}
              className="signature-pad"
              width="600"
              height="200"
              onMouseDown={startDrawing}
              onMouseMove={draw}
              onMouseUp={stopDrawing}
              onMouseLeave={stopDrawing}
              onTouchStart={startDrawing}
              onTouchMove={draw}
              onTouchEnd={stopDrawing}
            />
            <div className="proof-actions">
              <button type="button" className="btn-secondary" onClick={clearCanvas}>
                Clear
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={geo.capture}
                disabled={geo.loading}
              >
                {geo.loading ? "Capturing GPS…" : "Attach GPS"}
              </button>
              {geo.coords && (
                <small>📍 {geo.coords.lat}, {geo.coords.lng}</small>
              )}
            </div>
            {geo.error && <small className="alert error">{geo.error}</small>}
          </div>

          <div className="form-control">
            <label htmlFor="proof-notes">Driver notes</label>
            <textarea
              id="proof-notes"
              rows="2"
              placeholder="Add comments visible to dispatch..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <button type="submit" className="btn-primary" disabled={uploading}>
            {uploading ? "Uploading…" : "Upload Proof"}
          </button>
        </form>

        {order.proof_metadata && (
          <div className="info-card" style={{ marginTop: "16px" }}>
            <span>Last proof received</span>
            <strong>{formatRelativeTime(order.proof_captured_at)}</strong>
          </div>
        )}
      </div>
    </div>
  );
};

const DriverList = ({ drivers, onSelect }) => {
  if (!drivers || drivers.length === 0) {
    return <div className="empty-state">No drivers found.</div>;
  }

  return (
    <div className="drivers-grid">
      {drivers.map((driver) => (
        <div
          key={driver.id}
          className="driver-card"
          onClick={() => onSelect(driver.id)}
        >
          <div className="driver-card-header">
            <h3>{driver.name}</h3>
            <StatusBadge status={driver.status} />
          </div>
          <div className="driver-card-info">
            {driver.phone && <div className="meta">📞 {driver.phone}</div>}
            {driver.email && <div className="meta">✉️ {driver.email}</div>}
          </div>
        </div>
      ))}
    </div>
  );
};

const App = () => {
  const [drivers, setDrivers] = useState([]);
  const [selectedDriverId, setSelectedDriverId] = useState(null);
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [loadingGoogleMaps, setLoadingGoogleMaps] = useState(false);
  const [routeWaypoints, setRouteWaypoints] = useState([]); // Includes parking spots
  const [mobileViewMode, setMobileViewMode] = useState("list"); // "list" or "detail"
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 960);
      // Reset to list view when switching from mobile to desktop
      if (window.innerWidth >= 960) {
        setMobileViewMode("list");
      }
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const fetchDrivers = useCallback(async () => {
    setLoadingDrivers(true);
    setError(null);
    try {
      const data = await http.getJSON("/drivers/");
      setDrivers(data);
      // Auto-select first driver if none selected
      if (data.length > 0) {
        setSelectedDriverId((prevId) => prevId || data[0].id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingDrivers(false);
    }
  }, []);

  const fetchOrders = useCallback(async (driverId) => {
    if (!driverId) return;
    setRefreshing(true);
    setError(null);
    try {
      const data = await http.getJSON(`/orders/driver/orders?include_completed=false&driver_id=${driverId}`);
      setOrders(data);

      // Fetch route visualization data to get parking spots
      // Get the first active route for this driver
      if (data.length > 0 && data[0].route_id) {
        try {
          const routeData = await http.getJSON(`/routes/${data[0].route_id}/visualize`);
          if (routeData.waypoints) {
            setRouteWaypoints(routeData.waypoints);
          }
        } catch (err) {
          console.warn("Failed to fetch route visualization:", err);
          setRouteWaypoints([]);
        }
      } else {
        setRouteWaypoints([]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }, []);

  const handleStartRoute = useCallback(async () => {
    if (!selectedDriverId) return;
    setLoadingGoogleMaps(true);
    setError(null);
    try {
      const response = await http.getJSON(`/routes/driver/${selectedDriverId}/google-maps-url`);
      if (response.url) {
        window.open(response.url, "_blank");
      } else {
        setError("Failed to generate Google Maps URL");
      }
    } catch (err) {
      setError(err.message || "Failed to start route navigation");
    } finally {
      setLoadingGoogleMaps(false);
    }
  }, [selectedDriverId]);

  useEffect(() => {
    fetchDrivers();
  }, []); // Only run once on mount

  useEffect(() => {
    if (selectedDriverId) {
      fetchOrders(selectedDriverId);
      const interval = setInterval(() => fetchOrders(selectedDriverId), 60000);
      return () => clearInterval(interval);
    } else {
      setOrders([]);
      setSelectedOrderId(null);
    }
  }, [selectedDriverId]); // fetchOrders is stable, no need to include it

  useEffect(() => {
    if (!orders.length) {
      setSelectedOrderId(null);
      if (isMobile) setMobileViewMode("list");
      return;
    }
    if (!selectedOrderId) {
      setSelectedOrderId(orders[0].order.id);
      // Don't auto-navigate to detail on mobile
      return;
    }
    const stillExists = orders.some((assignment) => assignment.order.id === selectedOrderId);
    if (!stillExists) {
      setSelectedOrderId(orders[0].order.id);
      if (isMobile) setMobileViewMode("list");
    }
  }, [orders, selectedOrderId, isMobile]);

  const handleOrderSelect = useCallback((orderId) => {
    setSelectedOrderId(orderId);
    if (isMobile) {
      setMobileViewMode("detail");
    }
  }, [isMobile]);

  const selectedOrder = useMemo(() => {
    if (!orders.length) return null;
    return orders.find((assignment) => assignment.order.id === selectedOrderId) || orders[0];
  }, [orders, selectedOrderId]);

  const selectedDriver = useMemo(() => {
    if (!selectedDriverId) return null;
    return drivers.find((d) => d.id === selectedDriverId);
  }, [drivers, selectedDriverId]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Driver Companion</h1>
          <small>
            {selectedDriver
              ? `Viewing routes for ${selectedDriver.name}`
              : "Select a driver to view their assigned routes"}
          </small>
        </div>
        <div className="button-row">
          {selectedDriverId && (
            <>
              <button
                className="btn-primary"
                onClick={handleStartRoute}
                disabled={loadingGoogleMaps}
                style={{ fontSize: "1rem", padding: "12px 24px" }}
              >
                {loadingGoogleMaps ? "Loading…" : "🗺️ Start Route"}
              </button>
              <button
                className="btn-secondary"
                onClick={() => {
                  setSelectedDriverId(null);
                  setOrders([]);
                  setSelectedOrderId(null);
                }}
              >
                ← Back to Drivers
              </button>
              <button
                className="btn-secondary"
                onClick={() => fetchOrders(selectedDriverId)}
                disabled={refreshing}
              >
                {refreshing ? "Refreshing…" : "Sync now"}
              </button>
            </>
          )}
          {!selectedDriverId && (
            <button
              className="btn-secondary"
              onClick={fetchDrivers}
              disabled={loadingDrivers}
            >
              {loadingDrivers ? "Loading…" : "Refresh Drivers"}
            </button>
          )}
        </div>
      </header>

      {!selectedDriverId ? (
        <div className="panel" style={{ maxWidth: "1200px", margin: "0 auto" }}>
          {error && <div className="alert error">{error}</div>}
          <h2 style={{ marginBottom: "20px" }}>Select a Driver</h2>
          {loadingDrivers ? (
            <div className="empty-state">Loading drivers…</div>
          ) : (
            <DriverList drivers={drivers} onSelect={setSelectedDriverId} />
          )}
        </div>
      ) : (
        <>
          {isMobile && mobileViewMode === "detail" && selectedOrder ? (
            <div className="panel">
              <OrderDetail
                assignment={selectedOrder}
                driverId={selectedDriverId}
                onRefresh={() => fetchOrders(selectedDriverId)}
                onBack={() => setMobileViewMode("list")}
                showBackButton={true}
              />
            </div>
          ) : (
            <div className="content-layout">
              <aside className={`panel orders-panel ${isMobile && mobileViewMode === "detail" ? "mobile-hidden" : ""}`}>
                {error && <div className="alert error">{error}</div>}
                <div style={{ marginBottom: "16px" }}>
                  <strong>{selectedDriver?.name}'s Route</strong>
                  {(() => {
                    const sequencedCount = orders.filter(a => a.route_sequence != null).length;
                    return sequencedCount > 0 && (
                      <span style={{ marginLeft: "8px", color: "var(--text-secondary)" }}>
                        ({sequencedCount} active stop{sequencedCount !== 1 ? "s" : ""})
                      </span>
                    );
                  })()}
                </div>
                <RoutePlanOverview
                  orders={orders}
                  selectedOrderId={selectedOrder ? selectedOrder.order.id : null}
                  onSelect={handleOrderSelect}
                  onQuickStatusUpdate={() => fetchOrders(selectedDriverId)}
                  driverId={selectedDriverId}
                  routeWaypoints={routeWaypoints}
                />
              </aside>
              {!isMobile && (
                <main className="panel">
                  {selectedOrder ? (
                    <OrderDetail
                      assignment={selectedOrder}
                      driverId={selectedDriverId}
                      onRefresh={() => fetchOrders(selectedDriverId)}
                    />
                  ) : (
                    <div className="empty-state">
                      {orders.length === 0
                        ? "No active orders for this driver."
                        : "Select an order on the left to get started."}
                    </div>
                  )}
                </main>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

const root = ReactDOM.createRoot(document.getElementById("driver-app"));
root.render(<App />);
