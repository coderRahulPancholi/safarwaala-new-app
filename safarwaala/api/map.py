from safarwaala.utils import handle_error
from safarwaala.utils import handle_success
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
        # "place_id":        pred.get("place_id", ""),
        "place_id":       pred.get("reference", ""),
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
            return handle_success("Predictions fetched successfully", cached_data)
        
        api_key = _get_ola_api_key()
        default_location = location or "26.912434,75.787270" # Default to Jaipur
        
        params = {
            "location": default_location,
            "types": "",
            "language": "en",
            "radius": radius if radius else 10000,
            "withCentroid": "true",
            "rankBy": "popular",
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
            return handle_error("Maps API request timed out.", None)
        except requests.RequestException as exc:
            return handle_error(f"Maps API request failed: {exc}", None)
            
        if data.get("status") != "ok":
            return handle_error("Maps returned a non-ok status.", None)
            
        predictions = [_map_prediction(p) for p in data.get("predictions", [])]
        frappe.cache().set_value(cache_key, predictions, expires_in_sec=86400) # Cache for 24h
        
        return handle_success("Predictions fetched successfully", predictions)

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
        return handle_error("Maps API request timed out.", None)
    except requests.RequestException as exc:
        return handle_error(f"Maps API request failed: {exc}", None)

    if data.get("status") != "ok":
        return handle_error("Maps returned a non-ok status.", None)

    data = [_map_prediction(p) for p in data.get("predictions", [])]

    return handle_success("Predictions fetched successfully", data)


@frappe.whitelist(allow_guest=True)
def get_matrix_details(origin: str, destination: str):
    """
    Get routing directions between two references via OLA Maps basic directions API.
    
    Args:
        origin (str): Origin reference ID
        destination (str): Destination reference ID
    """
    try:
        if not origin or not destination:
            return handle_error("Both origin and destination references are required", None)
            
        # Add prefix
        origin_place_id = f"ola-platform:{origin}" if not origin.startswith("ola-platform:") else origin
        dest_place_id = f"ola-platform:{destination}" if not destination.startswith("ola-platform:") else destination
        
        # Get details
        from_details = get_place_details(origin_place_id)
        if from_details.get("status") == "error":
            return from_details
            
        to_details = get_place_details(dest_place_id)
        if to_details.get("status") == "error":
            return to_details
            
        from_lat = from_details.get("lat")
        from_lng = from_details.get("lng")
        to_lat = to_details.get("lat")
        to_lng = to_details.get("lng")
        
        if not from_lat or not from_lng or not to_lat or not to_lng:
            return handle_error("Could not fetch coordinates for the given locations", None)
            
        origin_coords = f"{from_lat},{from_lng}"
        dest_coords = f"{to_lat},{to_lng}"
        
        api_key = _get_ola_api_key()
        
        params = {
            "origin": origin_coords,
            "destination": dest_coords,
            "api_key": api_key,
        }
        
        response = requests.post(
            "https://api.olamaps.io/routing/v1/directions/basic",
            params=params,
            headers={"X-Request-Id": frappe.generate_hash(length=10)},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
            
        if data.get("status") != "SUCCESS":
            error_msg = data.get("error_message") or data.get("message") or "OLA Maps returned a non-success status."
            frappe.log_error(message=str(data), title="OLA Maps Directions API Error")
            return handle_error(error_msg, None)
            
        routes = data.get("routes", [])
        if not routes:
            return handle_error("No route found between the given locations.", None)
            
        leg = routes[0].get("legs", [{}])[0]
        distance_meters = leg.get("distance", 0)
        duration_seconds = leg.get("duration", 0)
        distance_km = round(distance_meters / 1000, 1) if distance_meters else 0
        duration_hours = round(duration_seconds / 3600, 1) if duration_seconds else 0   
        eligible_type = 'outstation'

        if from_details.get("city") == to_details.get("city"):
            eligible_type = 'local'
            
        result_data = {
                "distance_km": distance_km,
                "duration_seconds": duration_seconds,
                "distance_hours": duration_hours,
                "readable_distance": leg.get("readable_distance", f"{round(distance_meters / 1000, 1)} km"),
                "readable_duration": leg.get("readable_duration", ""),
                "from_city": from_details,
                "to_city": to_details,
                "eligible_type": eligible_type,
            }
        
        return handle_success("Matrix details fetched successfully", result_data)

    except requests.Timeout:
        return handle_error("OLA Maps Directions API request timed out.", None)
    except requests.RequestException as exc:
        err_msg = str(exc)
        if exc.response is not None:
            err_msg += f"\nResponse: {exc.response.text}"
        frappe.log_error(message=err_msg, title="OLA Maps Directions Request Failed")
        return handle_error(f"OLA Maps Directions API request failed: {exc}", None)
    except Exception as e:
        frappe.log_error("Get Matrix Details Error", str(e))
        return handle_error(f"An unexpected error occurred: {str(e)}", None)



def get_place_details(place_id: str) -> dict:
    try:
        api_key = _get_ola_api_key()
        params = {
            "place_id": place_id,
            "api_key": api_key,
            "language": "en",
        }
        
        response = requests.get(
            "https://api.olamaps.io/places/v1/details",
            params=params,
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "ok":
            error_msg = data.get("error_message") or data.get("message") or "OLA Maps returned a non-success status."
            frappe.log_error(message=str(data), title="OLA Maps Details API Error")
            return handle_error(error_msg, None)
        
        result = data.get("result", {})
        address_components = result.get("address_components", [])
        
        city = ""
        state = ""
        country = ""
        pin_code = ""
        
        for component in address_components:
            if not component.get("types"):
                continue
            if component.get("types")[0] == "locality":
                city = component.get("long_name", "")
            elif component.get("types")[0] == "administrative_area_level_1":
                state = component.get("long_name", "")
            elif component.get("types")[0] == "country":
                country = component.get("long_name", "")
            elif component.get("types")[0] == "postal_code":
                pin_code = component.get("long_name", "")
                
        lat = result.get("geometry", {}).get("location", {}).get("lat")
        lng = result.get("geometry", {}).get("location", {}).get("lng")
        
        return {
            "name": result.get("name", ""),
            "formatted_address": result.get("formatted_address", ""),
            "place_id": result.get("reference", ""),
            "city": city,
            "state": state,
            "country": country,
            "pin_code": pin_code,
            "lat": lat,
            "lng": lng,
            "types": result.get("types", []),
            "layers": result.get("layers", []),
        }
        
    except requests.Timeout:
        return handle_error("OLA Maps Details API request timed out.", None)
    except requests.RequestException as exc:
        err_msg = str(exc)
        if exc.response is not None:
            err_msg += f"\nResponse: {exc.response.text}"
        frappe.log_error(message=err_msg, title="OLA Maps Details Request Failed")
        return handle_error(f"OLA Maps Details API request failed: {exc}", None)
    except Exception as e:
        frappe.log_error(message=str(e), title="Get Place Details Error")
        return handle_error(f"An unexpected error occurred: {str(e)}", None)