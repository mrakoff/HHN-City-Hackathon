from typing import List, Dict, Tuple, Optional

# Try to import OR-Tools, but make it optional
try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("Note: OR-Tools not available. Using simple optimization algorithm.")

from .route_calculator import calculate_distance, calculate_route_metrics


def optimize_route_ortools(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    max_vehicles: int = 1
) -> Optional[List[int]]:
    """
    Optimize route using OR-Tools
    Returns list of order indices in optimal order
    """
    if not ORTOOLS_AVAILABLE:
        return None

    if not orders:
        return []

    # Create distance matrix
    num_locations = len(orders) + 1  # +1 for depot

    def distance_callback(from_index: int, to_index: int) -> int:
        """Returns the distance between the two nodes"""
        if from_index == to_index:
            return 0

        if from_index == 0:  # Depot
            point1 = depot
        else:
            point1 = orders[from_index - 1]

        if to_index == 0:  # Depot
            point2 = depot
        else:
            point2 = orders[to_index - 1]

        # Convert to integer (meters)
        distance_km = calculate_distance(
            point1['lat'], point1['lon'],
            point2['lat'], point2['lon']
        )
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
    orders: List[Dict[str, float]]
) -> List[int]:
    """
    Simple nearest-neighbor route optimization
    Returns list of order indices in optimized order
    """
    if not orders:
        return []

    unvisited = list(range(len(orders)))
    route = []
    current = depot

    while unvisited:
        nearest_idx = None
        nearest_distance = float('inf')

        for idx in unvisited:
            order = orders[idx]
            distance = calculate_distance(
                current['lat'], current['lon'],
                order['lat'], order['lon']
            )
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_idx = idx

        if nearest_idx is not None:
            route.append(nearest_idx)
            unvisited.remove(nearest_idx)
            current = orders[nearest_idx]

    return route


def optimize_route(
    depot: Dict[str, float],
    orders: List[Dict[str, float]],
    use_ortools: bool = True
) -> List[int]:
    """
    Optimize route order
    Returns list of order indices in optimal sequence
    """
    if not orders:
        return []

    if use_ortools and ORTOOLS_AVAILABLE:
        try:
            result = optimize_route_ortools(depot, orders)
            if result is not None:
                return result
        except Exception as e:
            print(f"OR-Tools optimization failed: {e}, falling back to simple algorithm")

    # Fallback to simple nearest-neighbor
    return optimize_route_simple(depot, orders)


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
