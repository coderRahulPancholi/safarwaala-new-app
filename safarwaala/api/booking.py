import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, strip_html

from safarwaala.safarwaala import booking_policy as bp
from safarwaala.utils import handle_success

# Doctypes `get_booking_details` is allowed to serve.
DETAIL_DOCTYPES = ("Bookings", "Duty Slips")

# Statuses driven by the duty-slip lifecycle (must exist in Status Master).
STATUS_ONGOING = "Ongoing"
STATUS_COMPLETED = "Completed"

# Internal commercials. `Document.as_dict()` ignores permlevel, so these are stripped by
# hand before any non-operator response leaves the server.
VENDOR_ONLY_FIELDS = (
    "vendor_rate_source",
    "override_vendor_rates",
    "vendor_per_km_rate",
    "vendor_per_hour_rate",
    "vendor_night_charge",
    "vendor_minimum_km_per_day",
    "vendor_base_amount",
    "vendor_night_charges",
    "vendor_extra_km_charges",
    "vendor_extra_hour_charges",
    "vendor_payable",
    "vendor_paid",
    "vendor_outstanding",
    "margin_amount",
    "margin_percent",
    "assigned_to",
)


# ── Shared helpers ──────────────────────────────────────────────────────────────
def _parse_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            frappe.throw(_("car_models must be a JSON list."), frappe.ValidationError)
    if not isinstance(value, (list, tuple)):
        frappe.throw(_("car_models must be a JSON list."), frappe.ValidationError)
    return list(value)


def _user_links(user):
    """The session user's linked Customer / Drivers / Vendors names."""
    return {
        "customer": frappe.db.get_value("Customer", {"linked_user": user}, "name"),
        "driver": frappe.db.get_value("Drivers", {"linked_user": user}, "name"),
        "vendor": frappe.db.get_value("Vendors", {"linked_user": user}, "name"),
    }


def _is_admin(user):
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _digits(value):
    return "".join(ch for ch in cstr(value) if ch.isdigit())


def _clean_message(exc):
    return strip_html(cstr(exc)).strip()


# ── Booking configuration (§2) ──────────────────────────────────────────────────
def _meta_options(doctype, fieldname):
    options = frappe.get_meta(doctype).get_field(fieldname).options or ""
    return [o.strip() for o in options.split("\n") if o.strip()]


def _build_config():
    rates = frappe.get_all("Car Models", fields=["seating_capacity", "per_km_rate", "hourly_rate"])
    seats = sorted({cint(r.seating_capacity) for r in rates if cint(r.seating_capacity)})

    def span(fieldname):
        values = [flt(r.get(fieldname)) for r in rates if flt(r.get(fieldname)) > 0]
        if not values:
            return {"min": 0, "max": 0}
        return {"min": int(min(values) // 1), "max": int(-(-max(values) // 1))}

    return {
        "booking_types": bp.get_booking_types(customer_facing=True),
        "trip_types": bp.get_trip_types(),
        "car_categories": _meta_options("Car Models", "category"),
        "fuel_types": _meta_options("Car Models", "fuel_type"),
        "transmissions": _meta_options("Car Models", "transmission"),
        "packages": frappe.get_all(
            "City Ride Package",
            fields=["name", "label", "distance", "duration"],
            order_by="duration asc, distance asc",
        ),
        "statuses": frappe.get_all("Status Master", pluck="name", order_by="creation asc"),
        "customer_types": _meta_options("Customer", "type"),
        "policy": bp.get_policy(),
        "seating_options": seats,
        "price_range": {**span("per_km_rate"), "unit": "per_km"},
        "hourly_price_range": {**span("hourly_rate"), "unit": "per_hour"},
    }


@frappe.whitelist(allow_guest=True)
def get_booking_config():
    """Everything the booking UI needs: booking types, vocabulary, policy, packages and filter facets."""
    data = bp.cached(bp.KEY_CONFIG, _build_config)
    return handle_success("Booking configuration fetched successfully", data)


# ── Fare quote (§5) ─────────────────────────────────────────────────────────────
def _quote_inputs(
    booking_type, pickup_datetime, return_datetime, trip_type, package_type, estimated_distance_km, office_to_pickup_km
):
    """Validate everything that does not depend on the car, once per request."""
    resolved = bp.resolve_booking_type(booking_type, customer_facing=True)
    pickup = bp.parse_datetime(pickup_datetime)
    return_dt = bp.parse_datetime(return_datetime)
    meta = bp.get_booking_type_meta(resolved)
    if meta["requires_return"] and not pickup:
        frappe.throw(_("Pickup date/time is required for {0} quotes.").format(meta["label"]), frappe.ValidationError)

    resolved_trip = bp.resolve_trip_type(resolved, trip_type, strict=True)
    distance = max(flt(estimated_distance_km), 0)
    return {
        "booking_type": resolved,
        "pickup": pickup,
        "return_dt": return_dt,
        "trip_type": resolved_trip,
        "package": bp.get_package(package_type) if meta["supports_packages"] else None,
        "estimated_distance_km": distance,
        "office_to_pickup_km": max(flt(office_to_pickup_km), 0),
        # Advisory on a quote: the UI blocks on these, `create_customer_booking` is what
        # refuses. A quote must still return a price so the customer can see what the trip
        # would cost once the dates are fixed.
        "schedule_error": bp.validate_schedule(pickup, return_dt, meta["requires_return"]),
        "feasibility": bp.check_trip_feasibility(distance, pickup, return_dt, resolved_trip),
    }


def _quote_for_car(inputs, car_model, policy):
    quote = bp.compute_fare(
        booking_type=inputs["booking_type"],
        car=bp.get_car_rates(car_model),
        package=inputs["package"],
        pickup=inputs["pickup"],
        return_dt=inputs["return_dt"],
        trip_type=inputs["trip_type"],
        estimated_distance_km=inputs["estimated_distance_km"],
        office_to_pickup_km=inputs["office_to_pickup_km"],
        policy=policy,
    )
    quote["car_model"] = car_model
    # Same itinerary for every car, so these are identical across a batch — carried on each
    # quote so the UI can block without a second round trip.
    quote["schedule_error"] = inputs["schedule_error"]
    quote["feasibility"] = inputs["feasibility"]
    return quote


@frappe.whitelist(allow_guest=True)
def get_fare_quote(
    booking_type,
    car_model=None,
    car_models=None,
    pickup_datetime=None,
    return_datetime=None,
    trip_type=None,
    package_type=None,
    estimated_distance_km=None,
    office_to_pickup_km=None,
):
    """Authoritative fare breakdown. ``car_models`` (JSON list) -> list of quotes, ``car_model`` -> one quote."""
    inputs = _quote_inputs(
        booking_type,
        pickup_datetime,
        return_datetime,
        trip_type,
        package_type,
        estimated_distance_km,
        office_to_pickup_km,
    )
    policy = bp.get_policy()

    if car_models not in (None, ""):
        quotes = []
        for model in dict.fromkeys(cstr(m) for m in _parse_list(car_models)):
            try:
                quotes.append(_quote_for_car(inputs, model, policy))
            except frappe.ValidationError as exc:
                frappe.clear_last_message()
                quotes.append({"car_model": model, "error": _clean_message(exc)})
        return handle_success("Fare quotes computed successfully", quotes)

    if not car_model:
        frappe.throw(_("car_model or car_models is required."), frappe.ValidationError)
    return handle_success("Fare quote computed successfully", _quote_for_car(inputs, car_model, policy))


# ── Create booking (§6) ─────────────────────────────────────────────────────────
def _office_to_pickup_km(pickup_latitude, pickup_longitude, client_value):
    """Dispatch distance from Settings office coords to the pickup point; falls back to the client value."""
    fallback = max(flt(client_value), 0)
    settings = bp.get_settings()
    office_lat, office_lng = flt(settings.get("lat")), flt(settings.get("long"))
    if not (office_lat or office_lng) or pickup_latitude in (None, "") or pickup_longitude in (None, ""):
        return fallback
    try:
        from safarwaala.api.map import get_route_distance_km

        return get_route_distance_km(f"{office_lat},{office_lng}", f"{pickup_latitude},{pickup_longitude}")
    except Exception:
        frappe.log_error(title="Office to pickup distance failed")
        return fallback


def _require(value, message):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        frappe.throw(message, frappe.ValidationError)


# A driver needs more than a word to find a pickup point.
MIN_ADDRESS_LENGTH = 6


def _check_address(value, label):
    if len(cstr(value).strip()) < MIN_ADDRESS_LENGTH:
        frappe.throw(
            _("{0} looks too short. Please give the full address.").format(label),
            frappe.ValidationError,
        )


@frappe.whitelist(allow_guest=True)
def create_customer_booking(
    booking_type,
    car_model,
    customer_name,
    customer_mobile,
    pickup_datetime,
    pickup_address,
    pickup_landmark=None,
    pickup_area=None,
    pickup_pincode=None,
    pickup_instructions=None,
    drop_landmark=None,
    drop_area=None,
    drop_pincode=None,
    drop_instructions=None,
    customer=None,
    pickup_latitude=None,
    pickup_longitude=None,
    drop_address=None,
    drop_latitude=None,
    drop_longitude=None,
    estimated_distance_km=None,
    estimated_duration_mins=None,
    package_type=None,
    trip_type=None,
    return_datetime=None,
    from_place_id=None,
    to_place_id=None,
    from_city=None,
    to_city=None,
    office_to_pickup_km=None,
):
    """Customer-facing booking creation. All money is recomputed server-side by the Bookings controller.

    Client-supplied rates, minimums, base amount and totals are not accepted parameters at all.
    """
    try:
        policy = bp.get_policy()
        resolved = bp.resolve_booking_type(booking_type, customer_facing=True)
        meta = bp.get_booking_type_meta(resolved)

        _require(customer_name, _("Customer name is required."))
        _require(pickup_address, _("Pickup address is required."))
        _check_address(pickup_address, _("Pickup address"))
        _require(pickup_datetime, _("Pickup date/time is required."))
        _require(car_model, _("Car model is required."))
        bp.check_mobile(customer_mobile, policy)
        if not frappe.db.exists("Car Models", car_model):
            frappe.throw(_("Car model {0} does not exist.").format(frappe.bold(cstr(car_model))), frappe.ValidationError)

        pickup = bp.parse_datetime(pickup_datetime)
        return_dt = bp.parse_datetime(return_datetime)
        bp.check_pickup_window(pickup, policy)
        if meta["requires_return"]:
            _require(return_datetime, _("Return date/time is required for {0} bookings.").format(meta["label"]))
        if return_dt and return_dt <= pickup:
            frappe.throw(_("Return date/time must be after the pickup date/time."), frappe.ValidationError)
        if meta["requires_drop"]:
            _require(drop_address, _("Drop address is required for {0} bookings.").format(meta["label"]))
            _check_address(drop_address, _("Drop address"))
        if meta["supports_packages"]:
            _require(package_type, _("A package is required for {0} bookings.").format(meta["label"]))
            bp.get_package(package_type)

        # Reject itineraries nobody could actually drive in the time booked.
        feasibility = bp.check_trip_feasibility(
            estimated_distance_km,
            pickup,
            return_dt,
            bp.resolve_trip_type(resolved, trip_type, strict=True),
            policy,
        )
        if not feasibility["feasible"]:
            frappe.throw(feasibility["message"], frappe.ValidationError)

        # Only the session user's own Customer record may be attached.
        linked_customer = None
        if frappe.session.user != "Guest":
            linked_customer = frappe.db.get_value("Customer", {"linked_user": frappe.session.user}, "name")

        values = {
            "doctype": "Bookings",
            "booking_type": resolved,
            "booking_status": bp.get_default_booking_status(),
            "trip_type": bp.resolve_trip_type(resolved, trip_type, strict=True),
            "car_model": car_model,
            "customer": linked_customer,
            "customer_name": cstr(customer_name).strip(),
            "customer_mobile": cstr(customer_mobile).strip(),
            "pickup_datetime": pickup,
            "pickup_address": pickup_address,
            "return_datetime": return_dt,
            "drop_address": drop_address,
            "from_place_id": from_place_id,
            "to_place_id": to_place_id,
            "from_city": bp.resolve_city(from_city),
            "to_city": bp.resolve_city(to_city),
        }
        # Address detail. The landmark falls back to the full line so a driver always has
        # something recognisable to look for.
        for fieldname, value in (
            ("pickup_landmark", pickup_landmark or pickup_address),
            ("pickup_area", pickup_area),
            ("pickup_pincode", pickup_pincode),
            ("pickup_instructions", pickup_instructions),
            ("drop_landmark", drop_landmark or drop_address),
            ("drop_area", drop_area),
            ("drop_pincode", drop_pincode),
            ("drop_instructions", drop_instructions),
            ("pickup_latitude", pickup_latitude),
            ("pickup_longitude", pickup_longitude),
            ("drop_latitude", drop_latitude),
            ("drop_longitude", drop_longitude),
        ):
            if value not in (None, ""):
                values[fieldname] = cstr(value).strip()
        if estimated_distance_km not in (None, ""):
            values["estimated_distance_km"] = max(flt(estimated_distance_km), 0)
        if estimated_duration_mins not in (None, ""):
            values["estimated_duration_mins"] = max(cint(flt(estimated_duration_mins)), 0)
        if meta["supports_packages"]:
            values["package_type"] = package_type
        if resolved == "Outstation":
            values["office_to_pickup_km"] = _office_to_pickup_km(
                pickup_latitude, pickup_longitude, office_to_pickup_km
            )

        doc = frappe.get_doc(values)
        doc.insert(ignore_permissions=True)

        return {
            "success": True,
            "message": "Booking created successfully",
            "data": {
                "name": doc.name,
                "booking_type": doc.booking_type,
                "trip_type": doc.trip_type,
                "booking_status": doc.booking_status,
                "base_amount": doc.base_amount,
                "night_charges": doc.night_charges,
                "tax_total": doc.tax_total,
                "grand_total": doc.grand_total,
            },
        }

    except frappe.ValidationError as exc:
        frappe.db.rollback()
        message = _clean_message(exc)
        frappe.clear_messages()
        return {"success": False, "message": message}
    except Exception as exc:
        frappe.db.rollback()
        frappe.log_error(title="create_customer_booking Error")
        frappe.clear_messages()
        return {"success": False, "message": _clean_message(exc)}


# ── Read bookings ───────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_my_bookings():
    """Bookings of the session user's linked Customer, Driver or Vendor."""
    user = frappe.session.user
    if user == "Guest":
        return handle_success("No bookings", [])

    links = _user_links(user)
    or_filters = []
    if links["driver"]:
        or_filters.append(["driver", "=", links["driver"]])
    if links["customer"]:
        or_filters.append(["customer", "=", links["customer"]])
    if links["vendor"]:
        or_filters.append(["assigned_to", "=", links["vendor"]])
    if not or_filters:
        return handle_success("No bookings", [])

    bookings = frappe.get_all(
        "Bookings",
        or_filters=or_filters,
        fields=[
            "name",
            "booking_status",
            "booking_type",
            "docstatus",
            "pickup_datetime",
            "return_datetime",
            "pickup_address",
            "drop_address",
            "from_city",
            "to_city",
            "trip_type",
            "grand_total",
            "customer_name",
            "car_model",
            "car_model_name",
            "creation",
        ],
        order_by="creation desc",
    )
    return handle_success("Bookings fetched successfully", bookings)


def _is_booking_party(doc, user):
    """Admin, or the booking's own customer / driver / assigned vendor."""
    if _is_admin(user):
        return True
    links = _user_links(user)
    return bool(
        (links["customer"] and doc.get("customer") == links["customer"])
        or (links["driver"] and doc.get("driver") == links["driver"])
        or (links["vendor"] and doc.get("assigned_to") == links["vendor"])
    )


def _is_trip_operator(doc, user):
    """Admin, the assigned driver, or the assigned vendor (customers may not run trips)."""
    if _is_admin(user):
        return True
    links = _user_links(user)
    return bool(
        (links["driver"] and doc.get("driver") == links["driver"])
        or (links["vendor"] and doc.get("assigned_to") == links["vendor"])
    )


def _mobile_matches(doc, customer_mobile):
    supplied = _digits(customer_mobile)
    stored = _digits(doc.get("customer_mobile"))
    return bool(supplied) and supplied == stored


@frappe.whitelist(allow_guest=True)
def get_booking_details(doctype, name, customer_mobile=None):
    """Full details of one booking. Owner/party, admin, or a guest presenting the booking's mobile."""
    if doctype not in DETAIL_DOCTYPES:
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("Booking not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc(doctype, name)
    user = frappe.session.user
    operator = False
    if doctype == "Bookings":
        operator = _is_trip_operator(doc, user)
        allowed = _is_booking_party(doc, user) or _mobile_matches(doc, customer_mobile)
    else:
        allowed = user != "Guest" and frappe.has_permission(doctype, "read", doc=doc)
        operator = allowed
    if not allowed:
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    details = doc.as_dict()

    if doc.get("driver"):
        driver = frappe.db.get_value("Drivers", doc.driver, ["full_name", "mobile"], as_dict=True)
        if driver:
            details["driver_details"] = {"name": driver.full_name, "mobile": driver.mobile}

    if doc.get("car"):
        car = frappe.db.get_value("Cars", doc.car, ["license_plate", "car_model"], as_dict=True)
        if car:
            car["car_number"] = car.license_plate
            details["car_details"] = car

    car_model = doc.get("car_model")
    if car_model:
        model = frappe.db.get_value(
            "Car Models", car_model, ["model_name", "seating_capacity", "luggage_capacity"], as_dict=True
        )
        if model:
            model["name"] = model.pop("model_name")
            details["car_model_details"] = model

    if doctype == "Bookings":
        # The customer may see their own money; vendor cost and margin are permlevel 1 and
        # are stripped below for everyone except an operator.
        details["payments"] = frappe.get_all(
            "Payments",
            filters={"booking": name, "docstatus": 1, "payment_direction": "Inbound"},
            fields=["name", "amount", "payment_date", "payment_mode", "reference_no"],
            order_by="payment_date asc",
        )
        if not operator:
            for field in VENDOR_ONLY_FIELDS:
                details.pop(field, None)

    return handle_success("Booking details fetched successfully", details)


# ── Duty slips ──────────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_duty_slip_details(booking_id):
    if not frappe.db.exists("Bookings", booking_id):
        return None

    booking = frappe.get_doc("Bookings", booking_id)
    if not _is_trip_operator(booking, frappe.session.user):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
    data = frappe.get_doc("Duty Slips", ds_name).as_dict() if ds_name else {}

    # Inject status for frontend logic
    data["status"] = booking.booking_status
    return data


@frappe.whitelist()
def manage_duty_slip(booking_id, action="create", **kwargs):
    """Create or update the Duty Slip of a booking and move the booking status with the trip."""
    try:
        if not frappe.db.exists("Bookings", booking_id):
            return {"success": False, "message": "Booking not found"}

        booking = frappe.get_doc("Bookings", booking_id)
        if not _is_trip_operator(booking, frappe.session.user):
            frappe.throw(_("Not permitted."), frappe.PermissionError)

        ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
        if ds_name:
            doc = frappe.get_doc("Duty Slips", ds_name)
            if doc.docstatus == 1:
                return {"success": False, "message": "Duty Slip is already submitted and cannot be edited."}
        else:
            if action not in ["create", "submit", "start_trip"]:
                return {"success": False, "message": "Duty Slip not found"}

            doc = frappe.new_doc("Duty Slips")
            doc.booking_type = "Bookings"
            doc.booking_id = booking_id
            doc.driver = booking.driver
            doc.car = booking.car
            doc.car_model = booking.car_model

        for fieldname in ("start_km", "end_km", "departure_datetime", "return_datetime"):
            if fieldname in kwargs:
                doc.set(fieldname, kwargs.get(fieldname))

        if action == "start_trip":
            doc.departure_datetime = frappe.utils.now_datetime()
        if action == "end_trip":
            doc.return_datetime = frappe.utils.now_datetime()

        doc.save(ignore_permissions=True)

        # Parent booking moves only after the duty slip is safely stored.
        if action == "start_trip":
            frappe.db.set_value(
                "Bookings",
                booking_id,
                {"booking_status": STATUS_ONGOING, "pickup_datetime": doc.departure_datetime},
            )
        if action == "end_trip":
            frappe.db.set_value(
                "Bookings",
                booking_id,
                {"booking_status": STATUS_COMPLETED, "return_datetime": doc.return_datetime},
            )

        if action == "submit" and doc.docstatus == 0:
            doc.submit()

        return {"success": True, "message": "Duty Slip updated", "data": doc.name}

    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Duty Slip Error: {str(e)}")
        return {"success": False, "message": _clean_message(e)}


@frappe.whitelist()
def submit_document(doctype, name):
    """Submit a document the session user is permitted to submit."""
    try:
        if not frappe.db.exists(doctype, name):
            return {"success": False, "message": f"{doctype} not found"}

        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            return {"success": False, "message": "Document is already submitted."}

        doc.check_permission("submit")
        doc.submit()

        return {"success": True, "message": f"{doctype} Submitted Successfully."}
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Submit Document Error: {str(e)}")
        return {"success": False, "message": _clean_message(e)}


# ── Dashboard ───────────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_dashboard_stats():
    try:
        user = frappe.session.user
        roles = frappe.get_roles(user)

        stats = {
            "active_drivers": 0,
            "total_vehicles": 0,
            "vendor_outstanding": 0,
            "customer_outstanding": 0,
            "upcoming_trips": 0,
            "duty_status": "Unknown",
        }

        if "Vendor" in roles or "System Manager" in roles:
            vendor_name = None
            if "System Manager" not in roles:
                vendor_name = frappe.db.get_value("Vendors", {"linked_user": user}, "name")

            driver_filters = {"disabled": 0}
            car_filters = {"disabled": 0}
            booking_filters = {"docstatus": ["<", 2]}
            if vendor_name:
                driver_filters["owner_vendor"] = vendor_name
                car_filters["belongs_to_vendor"] = vendor_name
                booking_filters["assigned_to"] = vendor_name

            stats["active_drivers"] = frappe.db.count("Drivers", filters=driver_filters)
            stats["total_vehicles"] = frappe.db.count("Cars", filters=car_filters)

            # Money still owed, from the booking settlement roll-up. Driver payments are
            # deliberately absent: the vendor pays its own drivers.
            rows = frappe.get_all(
                "Bookings",
                filters=booking_filters,
                fields=["vendor_outstanding", "customer_outstanding"],
            )
            stats["vendor_outstanding"] = flt(sum(flt(r["vendor_outstanding"]) for r in rows), 2)
            if "System Manager" in roles:
                stats["customer_outstanding"] = flt(
                    sum(flt(r["customer_outstanding"]) for r in rows), 2
                )
            else:
                # A vendor has no visibility of what the customer owes us.
                stats.pop("customer_outstanding", None)

        if "Driver" in roles:
            driver_doc_name = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
            if driver_doc_name:
                stats["upcoming_trips"] = frappe.db.count(
                    "Bookings", filters={"driver": driver_doc_name, "booking_status": "Confirmed"}
                )
                is_disabled = frappe.db.get_value("Drivers", driver_doc_name, "disabled")
                stats["duty_status"] = "Inactive" if is_disabled else "Active"
            else:
                stats["duty_status"] = "Not Found"
            # Drivers never see money figures.
            stats.pop("vendor_outstanding", None)
            stats.pop("customer_outstanding", None)

        return {"success": True, "data": stats}

    except Exception as e:
        frappe.log_error(f"Dashboard Stats Error: {str(e)}")
        return {"success": False, "message": str(e)}
