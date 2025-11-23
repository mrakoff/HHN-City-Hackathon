from typing import List, Dict, Tuple, Optional, Any
import logging

# Try to import OR-Tools, but make it optional
try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("Note: OR-Tools not available. Using simple optimization algorithm.")

# Try to import OSRM client
try:
    from .osrm_client import get_table, check_osrm_available
    OSRM_AVAILABLE = True
except ImportError:
    OSRM_AVAILABLE = False

from .route_calculator import calculate_distance, calculate_route_metrics, find_nearest_parking

logger = logging.getLogger(__name__)


def optimize_route_ortools(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    parking_locations: Optional[List[Dict[str, Any]]] = None,
    max_vehicles: int = 1
) -> Optional[List[int]]:
    """
    Optimize route using OR-Tools, considering parking spots if provided
    Returns list of order indices in optimal order
    """
    if not ORTOOLS_AVAILABLE:
        return None

    if not orders:
        return []

    # Pre-compute parking spots for each order if parking_locations provided
    order_parking = {}
    if parking_locations:
        for i, order in enumerate(orders):
            parking = find_nearest_parking(
                order['lat'], order['lon'],
                parking_locations
            )
            if parking:
                order_parking[i] = parking

    # Create distance matrix
    num_locations = len(orders) + 1  # +1 for depot

    # Build list of all points (depot + orders with parking if available)
    all_points = []
    point_indices = {}  # Map from (from_index, to_index) to point indices

    # Add depot as point 0
    all_points.append((depot['lat'], depot['lon']))

    # Add order points (with parking if available)
    for i, order in enumerate(orders):
        if i in order_parking:
            parking = order_parking[i]
            all_points.append((parking["latitude"], parking["longitude"]))
        else:
            all_points.append((order['lat'], order['lon']))

    # Try to get OSRM distance table for accurate road distances
    distance_table = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            distance_table = get_table(all_points)
            if distance_table:
                logger.debug("Using OSRM distance table for optimization")
        except Exception as e:
            logger.warning(f"OSRM table failed, using Haversine: {e}")

    def distance_callback(from_index: int, to_index: int) -> int:
        """Returns the distance between the two nodes, considering parking spots"""
        if from_index == to_index:
            return 0

        # Determine starting point index in all_points
        if from_index == 0:  # Depot
            start_idx = 0
        else:
            start_idx = from_index  # Order index + 1 (depot is 0)

        # Determine ending point index in all_points
        if to_index == 0:  # Depot
            end_idx = 0
        else:
            end_idx = to_index  # Order index + 1 (depot is 0)

        # Use OSRM distance table if available
        if distance_table and start_idx < len(distance_table) and end_idx < len(distance_table[start_idx]):
            distance_meters = distance_table[start_idx][end_idx]
            return int(distance_meters)

        # Fallback to Haversine
        start_point = all_points[start_idx]
        end_point = all_points[end_idx]
        distance_km = calculate_distance(start_point[0], start_point[1], end_point[0], end_point[1])
        return int(distance_km * 1000)  # Convert to meters

    # Create routing model
    manager = pywrapcp.RoutingIndexManager(num_locations, max_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Set search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 5

    # Solve
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        # Extract route
        route_indices = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route_indices.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))

        # Remove depot (index 0) and convert to order indices
        route_order_indices = [idx - 1 for idx in route_indices if idx > 0]
        return route_order_indices

    return None


def calculate_distance_matrix(points: List[Tuple[float, float]]) -> List[List[float]]:
    """Calculate distance matrix for all point pairs"""
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


def two_opt_swap(route: List[int], i: int, j: int) -> List[int]:
    """Perform 2-opt swap: reverse segment between i and j"""
    new_route = route[:i] + route[i:j+1][::-1] + route[j+1:]
    return new_route


def calculate_route_distance(route: List[int], distance_matrix: List[List[float]]) -> float:
    """Calculate total distance for a route"""
    if len(route) < 2:
        return 0.0

    total = 0.0
    current = 0  # Start at depot

    for order_idx in route:
        total += distance_matrix[current][order_idx + 1]  # +1 because depot is index 0
        current = order_idx + 1

    # Return to depot
    total += distance_matrix[current][0]
    return total


def optimize_route_2opt(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    parking_locations: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 100
) -> List[int]:
    """
    2-opt route optimization algorithm
    Returns list of order indices in optimized order
    """
    if not orders:
        return []

    # Pre-compute parking spots for each order if parking_locations provided
    order_parking = {}
    if parking_locations:
        for i, order in enumerate(orders):
            parking = find_nearest_parking(
                order['lat'], order['lon'],
                parking_locations
            )
            if parking:
                order_parking[i] = parking

    # Build list of all points
    depot_lat = depot.get('lat') or depot.get('latitude')
    depot_lon = depot.get('lon') or depot.get('longitude')
    all_points = [(depot_lat, depot_lon)]  # Depot is index 0
    point_to_order_idx = {0: None}

    for i, order in enumerate(orders):
        if i in order_parking:
            parking = order_parking[i]
            all_points.append((parking["latitude"], parking["longitude"]))
            point_to_order_idx[len(all_points) - 1] = i
        else:
            order_lat = order.get('lat') or order.get('latitude')
            order_lon = order.get('lon') or order.get('longitude')
            all_points.append((order_lat, order_lon))
            point_to_order_idx[len(all_points) - 1] = i

    # Get distance matrix (prefer OSRM, fallback to Haversine)
    distance_matrix = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            distance_matrix = get_table(all_points)
            if distance_matrix:
                # Convert meters to km for consistency
                distance_matrix = [[d / 1000.0 for d in row] for row in distance_matrix]
                logger.debug("Using OSRM distance matrix for 2-opt optimization")
        except Exception as e:
            logger.warning(f"OSRM table failed, using Haversine: {e}")

    if not distance_matrix:
        distance_matrix = calculate_distance_matrix(all_points)

    # Start with nearest neighbor solution
    initial_route = optimize_route_simple(depot, orders, parking_locations)
    best_route = initial_route.copy()
    best_distance = calculate_route_distance(best_route, distance_matrix)

    # 2-opt improvement
    improved = True
    iteration = 0
    improvements_made = 0

    logger.info(f"Starting 2-opt optimization on route with {len(best_route)} stops, initial distance: {best_distance:.2f}km")

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(len(best_route) - 1):
            for j in range(i + 2, len(best_route)):
                # Try 2-opt swap
                new_route = two_opt_swap(best_route, i, j)
                new_distance = calculate_route_distance(new_route, distance_matrix)

                if new_distance < best_distance:
                    best_route = new_route
                    best_distance = new_distance
                    improved = True
                    improvements_made += 1
                    logger.debug(f"2-opt improvement at iteration {iteration}: {new_distance:.2f}km (saved {(best_distance - new_distance):.2f}km)")
                    break

            if improved:
                break

    logger.info(f"2-opt optimization completed in {iteration} iterations, {improvements_made} improvements made, final distance: {best_distance:.2f}km")
    return best_route


def optimize_route_simple(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    parking_locations: Optional[List[Dict[str, Any]]] = None
) -> List[int]:
    """
    Simple nearest-neighbor route optimization, considering parking spots if provided
    Returns list of order indices in optimized order
    """
    if not orders:
        return []

    # Pre-compute parking spots for each order if parking_locations provided
    order_parking = {}
    if parking_locations:
        for i, order in enumerate(orders):
            parking = find_nearest_parking(
                order['lat'], order['lon'],
                parking_locations
            )
            if parking:
                order_parking[i] = parking

    # Build list of all points for OSRM distance table
    depot_lat = depot.get('lat') or depot.get('latitude')
    depot_lon = depot.get('lon') or depot.get('longitude')
    all_points = [(depot_lat, depot_lon)]
    point_to_order_idx = {0: None}  # Depot has no order index

    for i, order in enumerate(orders):
        if i in order_parking:
            parking = order_parking[i]
            all_points.append((parking["latitude"], parking["longitude"]))
            point_to_order_idx[len(all_points) - 1] = i
        else:
            order_lat = order.get('lat') or order.get('latitude')
            order_lon = order.get('lon') or order.get('longitude')
            all_points.append((order_lat, order_lon))
            point_to_order_idx[len(all_points) - 1] = i

    # Try to get OSRM distance table
    distance_matrix = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            distance_matrix = get_table(all_points)
            if distance_matrix:
                # Convert meters to km for consistency
                distance_matrix = [[d / 1000.0 for d in row] for row in distance_matrix]
        except Exception as e:
            logger.debug(f"OSRM table failed in simple optimizer: {e}")

    if not distance_matrix:
        distance_matrix = calculate_distance_matrix(all_points)

    unvisited = list(range(len(orders)))
    route = []
    current_idx = 0  # Start at depot (index 0 in all_points)

    while unvisited:
        nearest_order_idx = None
        nearest_distance = float('inf')
        nearest_point_idx = None

        for order_idx in unvisited:
            # Find the point index for this order
            target_point_idx = None
            for point_idx, mapped_order_idx in point_to_order_idx.items():
                if mapped_order_idx == order_idx:
                    target_point_idx = point_idx
                    break

            if target_point_idx is None:
                continue

            # Get distance from current position
            distance_km = distance_matrix[current_idx][target_point_idx]

            if distance_km < nearest_distance:
                nearest_distance = distance_km
                nearest_order_idx = order_idx
                nearest_point_idx = target_point_idx

        if nearest_order_idx is not None:
            route.append(nearest_order_idx)
            unvisited.remove(nearest_order_idx)
            current_idx = nearest_point_idx

    return route


def optimize_route(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    parking_locations: Optional[List[Dict[str, Any]]] = None,
    use_ortools: bool = True
) -> List[int]:
    """
    Optimize route order, considering parking spots if provided
    Returns list of order indices in optimal sequence
    """
    if not orders:
        return []

    if use_ortools and ORTOOLS_AVAILABLE:
        try:
            result = optimize_route_ortools(depot, orders, parking_locations)
            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"OR-Tools optimization failed: {e}, falling back to 2-opt algorithm")

    # Use 2-opt optimization (better than simple nearest neighbor)
    return optimize_route_2opt(depot, orders, parking_locations)


def calculate_route_improvement(
    original_route: List[int],
    optimized_route: List[int],
    depot: Dict[str, float],
    orders: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    Calculate improvement metrics between original and optimized route
    """
    def route_distance(route_indices: List[int]) -> float:
        if not route_indices:
            return 0.0

        total = 0.0
        current_lat = depot.get('lat') or depot.get('latitude')
        current_lon = depot.get('lon') or depot.get('longitude')

        for idx in route_indices:
            order = orders[idx]
            order_lat = order.get('lat') or order.get('latitude')
            order_lon = order.get('lon') or order.get('longitude')
            total += calculate_distance(current_lat, current_lon, order_lat, order_lon)
            current_lat, current_lon = order_lat, order_lon

        # Return to depot
        depot_lat = depot.get('lat') or depot.get('latitude')
        depot_lon = depot.get('lon') or depot.get('longitude')
        total += calculate_distance(current_lat, current_lon, depot_lat, depot_lon)

        return total

    original_dist = route_distance(original_route)
    optimized_dist = route_distance(optimized_route)

    improvement = original_dist - optimized_dist
    improvement_percent = (improvement / original_dist * 100) if original_dist > 0 else 0

    return {
        "original_distance_km": original_dist,
        "optimized_distance_km": optimized_dist,
        "distance_saved_km": improvement,
        "improvement_percent": improvement_percent
    }
