from typing import List, Dict, Tuple, Optional, Any
import math
import logging
from collections import defaultdict

# Try to import OSRM client
try:
    from .osrm_client import get_table, check_osrm_available
    OSRM_AVAILABLE = True
except ImportError:
    OSRM_AVAILABLE = False

from .route_calculator import calculate_distance

logger = logging.getLogger(__name__)


def calculate_distance_matrix(points: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Calculate distance matrix for all point pairs
    Returns matrix in kilometers
    """
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = calculate_distance(
                    points[i][0], points[i][1],
                    points[j][0], points[j][1]
                )
    return matrix


def cluster_orders_dbscan(
    orders: List[Dict[str, Any]],
    max_distance_km: float = 10.0,
    min_orders_per_cluster: int = 3
) -> List[List[int]]:
    """
    Cluster orders using DBSCAN-like algorithm based on geographic proximity

    Args:
        orders: List of orders with latitude/longitude
        max_distance_km: Maximum distance between orders in same cluster
        min_orders_per_cluster: Minimum orders required to form a cluster

    Returns:
        List of clusters, each cluster is a list of order indices
    """
    if not orders:
        return []

    # Extract coordinates
    coords = []
    valid_orders = []

    for i, order in enumerate(orders):
        lat = order.get('lat') or order.get('latitude')
        lon = order.get('lon') or order.get('longitude')
        if lat and lon:
            coords.append((lat, lon))
            valid_orders.append(i)

    if not coords:
        logger.warning("No valid coordinates found in orders")
        return []

    # Try to get OSRM distance matrix for accurate distances
    distance_matrix = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            osrm_matrix = get_table(coords)
            if osrm_matrix:
                # Convert meters to kilometers
                distance_matrix = [[d / 1000.0 for d in row] for row in osrm_matrix]
                logger.debug(f"Using OSRM distance matrix for clustering ({len(coords)} points)")
        except Exception as e:
            logger.warning(f"OSRM distance matrix failed, using Haversine: {e}")

    # Fallback to Haversine if OSRM not available
    if distance_matrix is None:
        distance_matrix = calculate_distance_matrix(coords)

    # Simple DBSCAN-like clustering
    n = len(coords)
    visited = [False] * n
    clusters = []
    noise = []

    def get_neighbors(point_idx: int) -> List[int]:
        """Get all neighbors within max_distance_km"""
        neighbors = []
        for j in range(n):
            if j != point_idx and distance_matrix[point_idx][j] <= max_distance_km:
                neighbors.append(j)
        return neighbors

    def expand_cluster(point_idx: int, neighbors: List[int], cluster: List[int]):
        """Expand cluster from a core point"""
        cluster.append(valid_orders[point_idx])
        visited[point_idx] = True

        i = 0
        while i < len(neighbors):
            neighbor_idx = neighbors[i]
            if not visited[neighbor_idx]:
                visited[neighbor_idx] = True
                neighbor_neighbors = get_neighbors(neighbor_idx)
                if len(neighbor_neighbors) >= min_orders_per_cluster - 1:
                    neighbors.extend(neighbor_neighbors)

            # Add to cluster if not already in another cluster
            if neighbor_idx not in [p for c in clusters for p in c if p < len(valid_orders)]:
                cluster.append(valid_orders[neighbor_idx])
            i += 1

    # Find clusters
    for i in range(n):
        if visited[i]:
            continue

        neighbors = get_neighbors(i)

        if len(neighbors) < min_orders_per_cluster - 1:
            # Mark as noise (will be added to smallest clusters later)
            noise.append(valid_orders[i])
        else:
            # Start new cluster
            cluster = []
            expand_cluster(i, neighbors, cluster)
            if len(cluster) >= min_orders_per_cluster:
                clusters.append(cluster)
            else:
                # Too small, add to noise
                noise.extend(cluster)

    # Assign noise points to nearest clusters
    if noise:
        logger.debug(f"Assigning {len(noise)} noise points to nearest clusters")
        for noise_idx in noise:
            if not clusters:
                # Create a new cluster for this single point
                clusters.append([noise_idx])
                continue

            # Find nearest cluster
            min_dist = float('inf')
            nearest_cluster_idx = 0

            # Get coordinates for noise point
            noise_order = orders[noise_idx]
            noise_lat = noise_order.get('lat') or noise_order.get('latitude')
            noise_lon = noise_order.get('lon') or noise_order.get('longitude')

            if not noise_lat or not noise_lon:
                continue

            for cluster_idx, cluster in enumerate(clusters):
                # Calculate average distance to cluster
                total_dist = 0.0
                count = 0
                for order_idx in cluster:
                    order = orders[order_idx]
                    order_lat = order.get('lat') or order.get('latitude')
                    order_lon = order.get('lon') or order.get('longitude')
                    if order_lat and order_lon:
                        dist = calculate_distance(noise_lat, noise_lon, order_lat, order_lon)
                        total_dist += dist
                        count += 1

                if count > 0:
                    avg_dist = total_dist / count
                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        nearest_cluster_idx = cluster_idx

            # Add to nearest cluster
            clusters[nearest_cluster_idx].append(noise_idx)

    logger.info(f"Clustered {len(orders)} orders into {len(clusters)} clusters")
    return clusters


def cluster_orders_kmeans(
    orders: List[Dict[str, Any]],
    num_clusters: int,
    max_iterations: int = 100
) -> List[List[int]]:
    """
    Cluster orders using K-means algorithm

    Args:
        orders: List of orders with latitude/longitude
        num_clusters: Number of clusters to create
        max_iterations: Maximum iterations for convergence

    Returns:
        List of clusters, each cluster is a list of order indices
    """
    if not orders or num_clusters <= 0:
        return []

    # Extract valid coordinates
    coords = []
    valid_indices = []

    for i, order in enumerate(orders):
        lat = order.get('lat') or order.get('latitude')
        lon = order.get('lon') or order.get('longitude')
        if lat and lon:
            coords.append((lat, lon))
            valid_indices.append(i)

    if len(coords) < num_clusters:
        # Not enough points, return one cluster per point
        return [[idx] for idx in valid_indices]

    # Initialize centroids randomly
    import random
    centroids = random.sample(coords, num_clusters)

    clusters = [[] for _ in range(num_clusters)]

    for iteration in range(max_iterations):
        # Assign points to nearest centroid
        new_clusters = [[] for _ in range(num_clusters)]

        for idx, (lat, lon) in enumerate(coords):
            min_dist = float('inf')
            nearest_centroid = 0

            for c_idx, (c_lat, c_lon) in enumerate(centroids):
                dist = calculate_distance(lat, lon, c_lat, c_lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_centroid = c_idx

            new_clusters[nearest_centroid].append(valid_indices[idx])

        # Update centroids
        converged = True
        for c_idx in range(num_clusters):
            if not new_clusters[c_idx]:
                continue

            avg_lat = sum(coords[valid_indices.index(idx)][0] for idx in new_clusters[c_idx]) / len(new_clusters[c_idx])
            avg_lon = sum(coords[valid_indices.index(idx)][1] for idx in new_clusters[c_idx]) / len(new_clusters[c_idx])

            old_centroid = centroids[c_idx]
            new_centroid = (avg_lat, avg_lon)

            if calculate_distance(old_centroid[0], old_centroid[1], new_centroid[0], new_centroid[1]) > 0.01:  # 10m threshold
                converged = False

            centroids[c_idx] = new_centroid

        clusters = new_clusters

        if converged:
            break

    # Filter out empty clusters
    clusters = [c for c in clusters if c]

    logger.info(f"K-means clustered {len(orders)} orders into {len(clusters)} clusters")
    return clusters


def cluster_orders(
    orders: List[Dict[str, Any]],
    method: str = "dbscan",
    max_distance_km: float = 10.0,
    min_orders_per_cluster: int = 3,
    max_orders_per_route: int = 40,
    num_clusters: Optional[int] = None
) -> List[List[int]]:
    """
    Main clustering function

    Args:
        orders: List of orders to cluster
        method: "dbscan" or "kmeans"
        max_distance_km: For DBSCAN, max distance between orders
        min_orders_per_cluster: Minimum orders per cluster
        max_orders_per_route: Maximum orders per route (will split large clusters)
        num_clusters: For K-means, number of clusters to create

    Returns:
        List of clusters, each cluster is a list of order indices
    """
    if not orders:
        return []

    # Choose clustering method
    if method == "kmeans" and num_clusters:
        clusters = cluster_orders_kmeans(orders, num_clusters)
    else:
        clusters = cluster_orders_dbscan(orders, max_distance_km, min_orders_per_cluster)

    # Split large clusters to respect max_orders_per_route
    final_clusters = []
    for cluster in clusters:
        if len(cluster) <= max_orders_per_route:
            final_clusters.append(cluster)
        else:
            # Split large cluster
            num_splits = (len(cluster) + max_orders_per_route - 1) // max_orders_per_route
            chunk_size = len(cluster) // num_splits

            for i in range(0, len(cluster), chunk_size):
                chunk = cluster[i:i + chunk_size]
                if chunk:
                    final_clusters.append(chunk)

            logger.info(f"Split large cluster of {len(cluster)} orders into {num_splits} smaller clusters")

    logger.info(f"Final clustering: {len(final_clusters)} clusters from {len(orders)} orders")
    return final_clusters
