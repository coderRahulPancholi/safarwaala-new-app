import frappe
import requests


def _get_ola_api_key() -> str:
    """Retrieve the OLA Maps API key from Frappe site config."""
    api_key = frappe.conf.get("ola_maps_api_key")
    if not api_key:
        frappe.throw(
            "OLA Maps API key is not configured. "
            "Set `ola_maps_api_key` in site_config.json.",
            frappe.AuthenticationError,
        )
    return api_key


def _map_prediction(pred: dict) -> dict:
    """Map a single OLA prediction object to a clean, minimal shape."""
    geometry = pred.get("geometry") or {}
    location = geometry.get("location") or {}
    formatting = pred.get("structured_formatting") or {}

    return {
        "place_id":        pred.get("place_id", ""),
        "reference":       pred.get("reference", ""),
        "description":     pred.get("description", ""),
        "main_text":       formatting.get("main_text", ""),
        "secondary_text":  formatting.get("secondary_text", ""),
        "types":           pred.get("types", []),
        "layer":           pred.get("layer", []),
        "lat":             location.get("lat"),
        "lng":             location.get("lng"),
    }


@frappe.whitelist(allow_guest=True)
def autocomplete(input: str = "", location: str = None, radius: int = None):
    """
    Proxy the OLA Maps autocomplete API and return a clean prediction list.

    Args:
        input    (str): Search text typed by the user.
        location (str): Optional bias point as "lat,lng" (e.g. "28.6,77.2").
        radius   (int): Optional bias radius in metres (used with `location`).

    Returns:
        {
            "status": "ok" | "error",
            "predictions": [
                {
                    "place_id": str,
                    "reference": str,
                    "description": str,
                    "main_text": str,
                    "secondary_text": str,
                    "types": list[str],
                    "layer": list[str],
                    "lat": float | None,
                    "lng": float | None,
                }
            ]
        }
    """
    if not input or not input.strip():
        cache_key = "safarwaala:ola:default_landmarks"
        cached_data = frappe.cache().get_value(cache_key)
        if cached_data:
            return {"status": "success", "data": cached_data}
        
        api_key = _get_ola_api_key()
        default_location = location or "26.9124,75.7873" # Default to Jaipur
        
        params = {
            "layers": "coarse",
            # "types": "restaurant",
            "location": default_location,
            "api_key": api_key,
        }
        
        try:
            response = requests.get(
                "https://api.olamaps.io/places/v1/nearbysearch",
                params=params,
                headers={"X-Request-Id": frappe.generate_hash(length=10)},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            frappe.throw("OLA Maps API request timed out.", frappe.ValidationError)
        except requests.RequestException as exc:
            frappe.throw(f"OLA Maps API request failed: {exc}", frappe.ValidationError)
            
        if data.get("status") != "ok":
            frappe.throw(
                data.get("error_message") or "OLA Maps returned a non-ok status.",
                frappe.ValidationError,
            )
            
        predictions = [_map_prediction(p) for p in data.get("predictions", [])]
        frappe.cache().set_value(cache_key, predictions, expires_in_sec=86400) # Cache for 24h
        
        return {"status": "success", "data": predictions}

    api_key = _get_ola_api_key()

    params = {
        "input":   input.strip(),
        "api_key": api_key,
    }
    if location:
        params["location"] = location
    if radius:
        params["radius"] = radius

    try:
        response = requests.get(
            "https://api.olamaps.io/places/v1/autocomplete",
            params=params,
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout:
        frappe.throw("OLA Maps API request timed out.", frappe.ValidationError)
    except requests.RequestException as exc:
        frappe.throw(f"OLA Maps API request failed: {exc}", frappe.ValidationError)

    if data.get("status") != "ok":
        frappe.throw(
            data.get("error_message") or "OLA Maps returned a non-ok status.",
            frappe.ValidationError,
        )

    data = [_map_prediction(p) for p in data.get("predictions", [])]

    return {
        "status": "success",
        "data": data,
    }


@frappe.whitelist(allow_guest=True)
def directions(origin: str, destination: str):
    """
    Get routing directions between two coordinates via OLA Maps basic directions API.
    
    Args:
        origin (str): Origin point "lat,lng"
        destination (str): Destination point "lat,lng"
    """
    if not origin or not destination:
        frappe.throw("Both origin and destination coordinates are required", frappe.ValidationError)
        
    api_key = _get_ola_api_key()
    
    params = {
        "origin": origin,
        "destination": destination,
        "api_key": api_key,
    }
    
    try:
        response = requests.post(
            "https://api.olamaps.io/routing/v1/directions/basic",
            params=params,
            headers={"X-Request-Id": frappe.generate_hash(length=10)},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout:
        frappe.throw("OLA Maps Directions API request timed out.", frappe.ValidationError)
    except requests.RequestException as exc:
        frappe.throw(f"OLA Maps Directions API request failed: {exc}", frappe.ValidationError)
        
    if data.get("status") != "SUCCESS":
        frappe.throw(
            data.get("error_message") or "OLA Maps returned a non-success status.",
            frappe.ValidationError,
        )
        
    routes = data.get("routes", [])
    if not routes:
        frappe.throw("No route found between the given locations.", frappe.ValidationError)
        
    leg = routes[0].get("legs", [{}])[0]
    distance_meters = leg.get("distance", 0)
    duration_seconds = leg.get("duration", 0)
    
    return {
        "status": "success",
        "data": {
            "distance_km": round(distance_meters / 1000, 1) if distance_meters else 0,
            "duration_seconds": duration_seconds,
            "readable_distance": leg.get("readable_distance", f"{round(distance_meters / 1000, 1)} km"),
            "readable_duration": leg.get("readable_duration", ""),
        }
    }

