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
    all_points = [(depot['lat'], depot['lon'])]
    point_to_order_idx = {0: None}  # Depot has no order index

    for i, order in enumerate(orders):
        if i in order_parking:
            parking = order_parking[i]
            all_points.append((parking["latitude"], parking["longitude"]))
            point_to_order_idx[len(all_points) - 1] = i
        else:
            all_points.append((order['lat'], order['lon']))
            point_to_order_idx[len(all_points) - 1] = i

    # Try to get OSRM distance table
    distance_table = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            distance_table = get_table(all_points)
        except Exception as e:
            logger.debug(f"OSRM table failed in simple optimizer: {e}")

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

            # Get distance using OSRM table or Haversine
            if distance_table and current_idx < len(distance_table) and target_point_idx < len(distance_table[current_idx]):
                distance_meters = distance_table[current_idx][target_point_idx]
                distance_km = distance_meters / 1000.0
            else:
                # Fallback to Haversine
                current_point = all_points[current_idx]
                target_point = all_points[target_point_idx]
                distance_km = calculate_distance(
                    current_point[0], current_point[1],
                    target_point[0], target_point[1]
                )

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
            print(f"OR-Tools optimization failed: {e}, falling back to simple algorithm")

    # Fallback to simple nearest-neighbor
    return optimize_route_simple(depot, orders, parking_locations)


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
        current = depot

        for idx in route_indices:
            order = orders[idx]
            total += calculate_distance(
                current['lat'], current['lon'],
                order['lat'], order['lon']
            )
            current = order

        # Return to depot
        total += calculate_distance(
            current['lat'], current['lon'],
            depot['lat'], depot['lon']
        )

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
