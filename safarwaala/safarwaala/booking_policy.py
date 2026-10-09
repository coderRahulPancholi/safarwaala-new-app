# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Shared booking core: vocabulary resolver, settings accessor, fare + tax engines.

Imported by the ``Bookings`` controller and by ``safarwaala.api.booking`` so that a
quote and a persisted booking are produced by the exact same code path.
"""

import math
import re

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.utils import add_to_date, cint, cstr, flt, get_datetime, now_datetime

BOOKINGS_DOCTYPE = "Bookings"
SETTINGS_DOCTYPE = "Safarwaala Settings"

# ── Cache ───────────────────────────────────────────────────────────────────────
CACHE_PREFIX = "safarwaala:booking:"
CACHE_TTL = 300
KEY_SETTINGS = CACHE_PREFIX + "settings"
KEY_CONFIG = CACHE_PREFIX + "config"


def clear_booking_cache(doc=None, method=None):
    """Drop every cached booking structure. Usable directly as a ``doc_events`` hook."""
    frappe.cache().delete_keys(CACHE_PREFIX + "*")


def cached(key, builder):
    cache = frappe.cache()
    value = cache.get_value(key)
    if value is None:
        value = builder()
        cache.set_value(key, value, expires_in_sec=CACHE_TTL)
    return value


# ── Settings ────────────────────────────────────────────────────────────────────
def _coerce(fieldtype, value):
    if fieldtype in ("Check", "Int"):
        return cint(value)
    if fieldtype in ("Float", "Currency", "Percent"):
        return flt(value)
    return cstr(value) if value is not None else None


def _build_settings():
    meta = frappe.get_meta(SETTINGS_DOCTYPE)
    stored = frappe.db.get_singles_dict(SETTINGS_DOCTYPE)
    out = {}
    for df in meta.fields:
        if df.fieldtype in no_value_fields:
            continue
        value = stored.get(df.fieldname)
        if value is None or value == "":
            value = df.default
        out[df.fieldname] = _coerce(df.fieldtype, value) if value not in (None, "") else None
    return out


def get_settings():
    """Cached ``Safarwaala Settings`` as a plain dict. Unset fields fall back to the DocField default."""
    return cached(KEY_SETTINGS, _build_settings)


def get_policy():
    """The ``policy`` block of the booking config (contract §2)."""
    s = get_settings()
    return {
        "currency": s.get("currency") or "INR",
        "currency_symbol": s.get("currency_symbol") or "",
        "min_advance_minutes": cint(s.get("min_advance_minutes")),
        "max_advance_days": cint(s.get("max_advance_days")),
        "gst_percent": flt(s.get("gst_percent")),
        "gst_label": s.get("gst_label") or "GST",
        "apply_gst": bool(cint(s.get("apply_gst"))),
        "default_min_km_per_day": flt(s.get("default_min_km_per_day")),
        "default_night_charge": flt(s.get("default_night_charge")),
        "dead_km_multiplier": flt(s.get("dead_km_multiplier")),
        "min_mobile_digits": cint(s.get("min_mobile_digits")),
        "local_radius_km": flt(s.get("local_radius_km")),
        "avg_speed_kmph": flt(s.get("avg_speed_kmph")) or 45.0,
        "max_driving_hours_per_day": flt(s.get("max_driving_hours_per_day")) or 13.0,
        "min_rest_hours_at_destination": flt(s.get("min_rest_hours_at_destination")),
        "feasibility_buffer_percent": flt(s.get("feasibility_buffer_percent")),
    }


def get_default_booking_status():
    return get_settings().get("default_booking_status") or "Pending"


def split_lines(text):
    return [line.strip() for line in cstr(text).splitlines() if line.strip()]


# ── Vocabulary ──────────────────────────────────────────────────────────────────
# Annotations for booking-type values. The list of *valid* values always comes from the
# Bookings.booking_type Select options; entries here only describe values that exist there.
BOOKING_TYPE_META = {
    "Outstation": {
        "code": "outstation",
        "label": "Outstation",
        "aliases": ("outstation", "out station", "out-station"),
        "requires_drop": True,
        "requires_return": True,
        "supports_packages": False,
        # Driven by `Safarwaala Settings.outstation_trip_types`, not hardcoded, so an
        # operator can open up one-way outstation without a code change.
        "trip_types_setting": "outstation_trip_types",
        "inclusions_key": "outstation_inclusions",
        "exclusions_key": "outstation_exclusions",
    },
    "Local": {
        "code": "hourly",
        "label": "Hourly Rental",
        "aliases": ("local", "hourly", "hourly rental", "hourly-rental"),
        "requires_drop": False,
        "requires_return": False,
        "supports_packages": True,
        # A city rental starts and ends at the pickup; there is no return leg to price.
        "trip_types_setting": None,
        "fixed_trip_types": ("OneWay",),
        "inclusions_key": "local_inclusions",
        "exclusions_key": "local_exclusions",
    },
    "Package": {
        "code": "package",
        "label": "Fixed Package",
        "aliases": ("package", "fixed", "fixed package", "fixed-package"),
        "requires_drop": False,
        "requires_return": False,
        "supports_packages": False,
        "trip_types_setting": None,
        "fixed_trip_types": None,  # any trip type the DocType allows
        "inclusions_key": None,
        "exclusions_key": None,
    },
}

# `outstation_trip_types` setting value -> the trip types it permits.
TRIP_TYPE_POLICY = {
    "RoundTrip Only": ("RoundTrip",),
    "OneWay Only": ("OneWay",),
    "Both": ("RoundTrip", "OneWay"),
}


def select_options(doctype, fieldname):
    options = frappe.get_meta(doctype).get_field(fieldname).options or ""
    return [o.strip() for o in options.split("\n") if o.strip()]


def get_trip_types():
    return select_options(BOOKINGS_DOCTYPE, "trip_type")


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", cstr(value).lower()).strip("-")


def get_booking_type_meta(value):
    """Metadata for a DocType booking_type value (synthesised for values with no annotation)."""
    meta = BOOKING_TYPE_META.get(value)
    if meta:
        return meta
    return {
        "code": _slug(value),
        "label": value,
        "aliases": (cstr(value).lower(),),
        "requires_drop": False,
        "requires_return": False,
        "supports_packages": False,
        "trip_types_setting": None,
        "fixed_trip_types": None,
        "inclusions_key": None,
        "exclusions_key": None,
    }


def allowed_trip_types(booking_type):
    """Trip types this booking type currently permits.

    Always intersected with the live ``Bookings.trip_type`` Select options, so the DocType
    stays the source of truth for what a trip type *is*, while ``Safarwaala Settings``
    decides which of them a product offers today.
    """
    available = get_trip_types()
    meta = get_booking_type_meta(booking_type)

    setting_key = meta.get("trip_types_setting")
    if setting_key:
        choice = cstr(get_settings().get(setting_key)) or "RoundTrip Only"
        wanted = TRIP_TYPE_POLICY.get(choice) or TRIP_TYPE_POLICY["RoundTrip Only"]
    else:
        wanted = meta.get("fixed_trip_types")

    if not wanted:
        return tuple(available)

    resolved = tuple(t for t in wanted if t in available)
    # Never return an empty set: fall back to whatever the DocType allows.
    return resolved or tuple(available)


def get_booking_type_values():
    """Valid booking_type values straight from the DocType Select options."""
    return select_options(BOOKINGS_DOCTYPE, "booking_type")


def get_booking_types(customer_facing=False):
    """Booking types as exposed on the wire (contract §2). ``Package`` is gated on Settings."""
    settings = get_settings()
    out = []
    for value in get_booking_type_values():
        if customer_facing and value == "Package" and not cint(settings.get("enable_package_bookings")):
            continue
        meta = get_booking_type_meta(value)
        out.append(
            {
                "value": value,
                "code": meta["code"],
                "label": meta["label"],
                "requires_drop": meta["requires_drop"],
                "requires_return": meta["requires_return"],
                "supports_packages": meta["supports_packages"],
                "allowed_trip_types": list(allowed_trip_types(value)),
                "default_trip_type": default_trip_type(value),
                "inclusions": split_lines(settings.get(meta["inclusions_key"])) if meta["inclusions_key"] else [],
                "exclusions": split_lines(settings.get(meta["exclusions_key"])) if meta["exclusions_key"] else [],
            }
        )
    return out


def resolve_booking_type(raw, customer_facing=False):
    """Map a DocType value / wire code / label / alias (any casing) to the canonical DocType value."""
    values = get_booking_type_values()
    needle = cstr(raw).strip().lower()
    candidates = values if not customer_facing else [t["value"] for t in get_booking_types(True)]
    if needle:
        for value in candidates:
            meta = get_booking_type_meta(value)
            names = {value.lower(), meta["code"], meta["label"].lower(), *meta["aliases"]}
            if needle in names:
                return value
    valid = ", ".join(get_booking_type_meta(v)["code"] for v in candidates)
    frappe.throw(
        _("Unknown booking type {0}. Valid booking types: {1}").format(frappe.bold(cstr(raw)), valid),
        frappe.ValidationError,
    )


def default_trip_type(booking_type):
    """The trip type to assume when the caller does not state one."""
    return (allowed_trip_types(booking_type) or [None])[0]


def resolve_trip_type(booking_type, trip_type=None, strict=False):
    """Return a valid trip type. With ``strict`` a type outside the booking type's allowed set is rejected."""
    meta = get_booking_type_meta(booking_type)
    if not cstr(trip_type).strip():
        return default_trip_type(booking_type)
    valid = {t.lower(): t for t in get_trip_types()}
    resolved = valid.get(cstr(trip_type).strip().lower())
    if not resolved:
        frappe.throw(
            _("Unknown trip type {0}. Valid trip types: {1}").format(
                frappe.bold(cstr(trip_type)), ", ".join(valid.values())
            ),
            frappe.ValidationError,
        )
    permitted = allowed_trip_types(booking_type)
    if strict and resolved not in permitted:
        frappe.throw(
            _("{0} bookings only support: {1}").format(meta["label"], ", ".join(permitted)),
            frappe.ValidationError,
        )
    return resolved


# ── Input validation shared by controller and API ───────────────────────────────
def parse_datetime(value):
    """``datetime`` from a string/datetime (``None`` when blank); anything unparsable is a ValidationError."""
    if not cstr(value).strip():
        return None
    try:
        return get_datetime(value)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid date/time: {0}").format(frappe.bold(cstr(value))), frappe.ValidationError)


def resolve_city(name):
    """``City Master`` record name matching ``name`` case-insensitively, else ``None``."""
    needle = cstr(name).strip()
    if not needle:
        return None
    if frappe.db.exists("City Master", needle):
        return needle
    return frappe.db.get_value("City Master", {"city_name": needle}, "name") or next(
        (c for c in frappe.get_all("City Master", pluck="name") if c.lower() == needle.lower()), None
    )


def check_pickup_window(pickup, policy=None):
    """Pickup must be at least ``min_advance_minutes`` ahead and at most ``max_advance_days`` ahead."""
    policy = policy or get_policy()
    now = now_datetime()
    earliest = add_to_date(now, minutes=policy["min_advance_minutes"])
    latest = add_to_date(now, days=policy["max_advance_days"])
    if pickup < earliest:
        frappe.throw(
            _("Pickup time must be at least {0} minutes from now.").format(policy["min_advance_minutes"]),
            frappe.ValidationError,
        )
    if pickup > latest:
        frappe.throw(
            _("Pickup time cannot be more than {0} days from now.").format(policy["max_advance_days"]),
            frappe.ValidationError,
        )


def validate_schedule(pickup, return_dt, requires_return, policy=None):
    """The booking-window rules as a message instead of an exception.

    ``check_pickup_window`` throws, which is right at creation but wrong while quoting: a
    quote should be able to say "these dates are invalid" and still return a response, so
    the UI can block the customer *before* they fill in traveller details rather than
    failing on the final click.

    Returns ``None`` when the schedule is bookable, otherwise the reason.
    """
    policy = policy or get_policy()

    if not pickup:
        return _("Choose a pickup date and time.")

    now = now_datetime()
    if pickup < add_to_date(now, minutes=policy["min_advance_minutes"]):
        return _("Pickup must be at least {0} minutes from now.").format(policy["min_advance_minutes"])
    if pickup > add_to_date(now, days=policy["max_advance_days"]):
        return _("Pickup cannot be more than {0} days from now.").format(policy["max_advance_days"])

    if requires_return and not return_dt:
        return _("Choose a return date and time.")
    if return_dt and pickup and return_dt <= pickup:
        return _("Return date/time must be after the pickup date/time.")

    return None


def check_mobile(mobile, policy=None):
    policy = policy or get_policy()
    digits = re.sub(r"\D", "", cstr(mobile))
    if len(digits) < policy["min_mobile_digits"]:
        frappe.throw(
            _("Mobile number must have at least {0} digits.").format(policy["min_mobile_digits"]),
            frappe.ValidationError,
        )
    return digits


# ── Rate sources ────────────────────────────────────────────────────────────────
CAR_RATE_FIELDS = (
    "name",
    "model_name",
    "per_km_rate",
    "local_km_rate",
    "minimum_km_per_day",
    "hourly_rate",
    "night_surcharge",
)


def get_car_rates(car_model):
    """Rate fields of a Car Models record as a dict."""
    car = frappe.db.get_value("Car Models", car_model, list(CAR_RATE_FIELDS), as_dict=True) if car_model else None
    if not car:
        frappe.throw(_("Car model {0} does not exist.").format(frappe.bold(cstr(car_model))), frappe.ValidationError)
    return car


def get_package(package_type):
    """City Ride Package as ``{name, label, distance, duration}``."""
    pkg = (
        frappe.db.get_value("City Ride Package", package_type, ["name", "label", "distance", "duration"], as_dict=True)
        if package_type
        else None
    )
    if not pkg:
        frappe.throw(
            _("Package {0} does not exist.").format(frappe.bold(cstr(package_type))), frappe.ValidationError
        )
    return pkg


# ── Tax engine ──────────────────────────────────────────────────────────────────
def _row_get(row, key):
    return row.get(key)


def _row_set(row, key, value):
    if isinstance(row, dict):
        row[key] = value
    else:
        row.set(key, value)


def apply_taxes(doc_or_rows, taxable, policy=None, manage_gst=True):
    """Compute tax rows in place and return ``tax_total``.

    ``doc_or_rows`` is either a ``Bookings`` document (rows live in ``tax_and_charges``) or a
    plain list of row dicts. Row semantics:
      * ``Actual`` or a row with no rate -> ``amount`` is honoured as entered;
      * ``Total``     -> ``taxable * rate / 100``;
      * ``Prev Row``  -> ``previous row running total * rate / 100`` (first row: taxable).
    The row carrying the GST label always uses ``policy.gst_percent``. When ``apply_gst`` is on
    and no GST-labelled row exists, one is inserted. ``total`` is the running total per row.
    """
    policy = policy or get_policy()
    is_doc = not isinstance(doc_or_rows, list)
    rows = doc_or_rows.get("tax_and_charges") if is_doc else doc_or_rows
    if rows is None:
        rows = []
    gst_label = policy["gst_label"]
    gst_active = manage_gst and policy["apply_gst"] and policy["gst_percent"] > 0

    def is_gst(row):
        return cstr(_row_get(row, "remark")).strip().lower() == gst_label.strip().lower()

    if gst_active and not any(is_gst(r) for r in rows):
        new_row = {"apply_on": "Total", "rate": policy["gst_percent"], "remark": gst_label}
        if is_doc:
            doc_or_rows.append("tax_and_charges", new_row)
            rows = doc_or_rows.get("tax_and_charges")
        else:
            rows.append(new_row)

    taxable = flt(taxable, 2)
    running = taxable
    tax_total = 0.0
    for row in rows:
        rate = policy["gst_percent"] if (gst_active and is_gst(row)) else flt(_row_get(row, "rate"))
        apply_on = _row_get(row, "apply_on") or ("Total" if rate else "Actual")
        if apply_on == "Actual" or not rate:
            amount = flt(_row_get(row, "amount"), 2)
        elif apply_on == "Prev Row":
            amount = flt(running * rate / 100, 2)
        else:
            amount = flt(taxable * rate / 100, 2)
        running = flt(running + amount, 2)
        tax_total += amount
        if apply_on != "Actual" and rate:
            _row_set(row, "rate", rate)
        if not _row_get(row, "apply_on"):
            _row_set(row, "apply_on", apply_on)
        _row_set(row, "amount", amount)
        _row_set(row, "total", running)
    return flt(tax_total, 2)


# ── Fare engine ─────────────────────────────────────────────────────────────────
def _hours_between(start, end):
    if not start or not end:
        return 0.0
    return max((end - start).total_seconds() / 3600.0, 0.0)


def _days_for(hours):
    return max(int(math.ceil(round(hours / 24.0, 6))), 1)


def _fmt(value):
    """Number without a trailing .0 for display."""
    value = flt(value, 2)
    return str(int(value)) if value == int(value) else str(value)


# ── Trip feasibility ────────────────────────────────────────────────────────────
# A customer can pick Jaipur -> Manali (713 km) and ask for it back the next day. That is
# ~32 hours of driving inside a 24-hour window: not a cheap trip, an impossible one.
# Accepting it means a booking nobody can run, so the itinerary is checked against a
# planning speed and a legal daily driving limit, both from Safarwaala Settings.
#
# Drive time is derived from DISTANCE, not from the routing API's duration: OLA reports
# ~21 km/h even on highways (Jaipur->Delhi, 256 km, comes back as 11.7 h), which would make
# almost every long trip look impossible.


def estimate_drive_hours(distance_km, policy=None):
    """One-way driving hours for ``distance_km`` at the configured planning speed."""
    policy = policy or get_policy()
    speed = flt(policy.get("avg_speed_kmph")) or 45.0
    return flt(distance_km) / speed if speed > 0 else 0.0


def check_trip_feasibility(
    distance_km,
    pickup,
    return_dt,
    trip_type="RoundTrip",
    policy=None,
):
    """Can this itinerary actually be driven in the time booked?

    Returns ``{feasible, severity, message, drive_hours, required_hours, available_hours,
    minimum_days, suggested_return}``. ``severity`` is ``ok`` | ``tight`` | ``impossible``.
    A missing distance or return makes the check inconclusive rather than failing closed —
    the caller should not block a booking just because routing was unavailable.
    """
    policy = policy or get_policy()
    out = {
        "feasible": True,
        "severity": "ok",
        "message": "",
        "drive_hours": 0.0,
        "required_hours": 0.0,
        "available_hours": 0.0,
        "minimum_days": 1,
        "suggested_return": None,
    }

    distance_km = flt(distance_km)
    pickup = parse_datetime(pickup)
    return_dt = parse_datetime(return_dt)
    if distance_km <= 0 or not pickup or not return_dt:
        return out

    legs = 2 if trip_type == "RoundTrip" else 1
    max_per_day = flt(policy.get("max_driving_hours_per_day")) or 13.0
    buffer_factor = 1.0 + max(flt(policy.get("feasibility_buffer_percent")), 0.0) / 100.0

    drive_hours = estimate_drive_hours(distance_km, policy) * legs
    available_hours = _hours_between(pickup, return_dt)

    # How many days of driving this needs at the daily cap. A trip only has to absorb an
    # overnight (and the driver's rest at the destination) once the driving genuinely does
    # not fit inside the window — otherwise a routine same-day run like Jaipur->Delhi and
    # back, 11 h of driving in a 16 h window, would be called impossible.
    driving_days = max(math.ceil(drive_hours / max_per_day), 1) if max_per_day > 0 else 1
    if driving_days > 1:
        rest = flt(policy.get("min_rest_hours_at_destination")) if legs == 2 else 0.0
        overnight_hours = (driving_days - 1) * (24.0 - max_per_day)
        required_hours = drive_hours + rest + overnight_hours
    else:
        required_hours = drive_hours

    out["drive_hours"] = flt(drive_hours, 1)
    out["required_hours"] = flt(required_hours, 1)
    out["available_hours"] = flt(available_hours, 1)
    out["minimum_days"] = _days_for(required_hours)
    out["suggested_return"] = add_to_date(pickup, hours=math.ceil(required_hours), as_string=True)

    if available_hours >= required_hours * buffer_factor:
        return out

    readable_drive = _fmt(flt(drive_hours, 1))
    if available_hours < required_hours:
        out.update(
            feasible=False,
            severity="impossible",
            message=_(
                "This trip needs about {0} hours of driving ({1} km {2}), but the return is only "
                "{3} hours after pickup. Allow at least {4} day(s)."
            ).format(
                readable_drive,
                _fmt(distance_km * legs),
                _("round trip") if legs == 2 else _("one way"),
                _fmt(flt(available_hours, 1)),
                out["minimum_days"],
            ),
        )
        return out

    out.update(
        severity="tight",
        message=_(
            "About {0} hours of driving in a {1} hour window leaves very little time at the "
            "destination. Consider a longer trip."
        ).format(readable_drive, _fmt(flt(available_hours, 1))),
    )
    return out


def _empty_fare():
    return {
        "days": 0,
        "nights": 0,
        "chargeable_km": 0,
        "min_km": 0,
        "min_hours": 0,
        "per_km_rate": 0.0,
        "per_hour_rate": 0.0,
        "night_rate": 0.0,
        "base_amount": 0.0,
        "extra_km_charges": 0.0,
        "extra_hour_charges": 0.0,
        "night_charges": 0.0,
        "dead_km": 0.0,
        "route_km": 0.0,
        "total_km": 0,
        "actual_hours": 0.0,
    }


def compute_fare(
    booking_type,
    car,
    package=None,
    pickup=None,
    return_dt=None,
    trip_type=None,
    estimated_distance_km=None,
    office_to_pickup_km=None,
    start_km=None,
    end_km=None,
    policy=None,
    tax_target=None,
    rates=None,
    apply_tax=True,
):
    """The single fare implementation (contract §4).

    ``car`` is a dict with the Car Models rate fields, ``package`` a dict with
    ``distance``/``duration`` (required for ``Local``). ``tax_target`` is a Bookings document or a
    list of tax-row dicts that ``apply_taxes`` updates in place; ``None`` quotes with only the
    auto GST row. Returns the §5 breakdown dict. For ``Package`` bookings no money is computed;
    the vendor-entered ``grand_total`` is authoritative.

    ``rates`` overrides the per-km / per-hour / night / minimum-km figures taken from ``car``.
    That is how the *vendor* side of a booking is costed: identical trip geometry (days,
    nights, chargeable km, package hours), different rates. There is exactly one fare
    formula. ``apply_tax=False`` skips the tax engine, since vendor cost is pre-tax.
    """
    policy = policy or get_policy()
    pickup = parse_datetime(pickup)
    return_dt = parse_datetime(return_dt)
    meta = get_booking_type_meta(booking_type)
    trip_type = trip_type or default_trip_type(booking_type)
    car = car or {}
    fare = _empty_fare()
    symbol = policy["currency_symbol"]

    # A rate override wins over the car's own rate card; `None`/absent falls back to the car.
    overrides = rates or {}

    def rate(key, car_key):
        value = overrides.get(key)
        return flt(value) if value not in (None, "") else flt(car.get(car_key))

    start_km = flt(start_km)
    end_km = flt(end_km)
    driven_km = max(end_km - start_km, 0) if end_km else 0
    fare["total_km"] = int(round(driven_km))
    breakdown = []
    note = ""

    if booking_type == "Local":
        if not package:
            frappe.throw(_("A package is required for {0} bookings.").format(meta["label"]), frappe.ValidationError)
        min_hours = flt(package.get("duration"))
        min_km = flt(package.get("distance"))
        per_hour_rate = rate("per_hour_rate", "hourly_rate")
        per_km_rate = rate("per_km_rate", "local_km_rate")
        actual_hours = _hours_between(pickup, return_dt)
        base_amount = flt(min_hours * per_hour_rate, 2)
        extra_hour_charges = flt(max(actual_hours - min_hours, 0) * per_hour_rate, 2)
        extra_km_charges = flt(max(driven_km - min_km, 0) * per_km_rate, 2)
        fare.update(
            min_hours=min_hours,
            min_km=int(round(min_km)),
            chargeable_km=int(round(min_km)),
            per_hour_rate=per_hour_rate,
            per_km_rate=per_km_rate,
            base_amount=base_amount,
            extra_hour_charges=extra_hour_charges,
            extra_km_charges=extra_km_charges,
            actual_hours=flt(actual_hours, 2),
            days=1,
        )
        breakdown.append(
            {"label": _("Package"), "value": f"{_fmt(min_hours)} hrs / {_fmt(min_km)} km"}
        )
        breakdown.append(
            {
                "label": _("Base fare"),
                "value": f"{_fmt(min_hours)} hrs × {symbol}{_fmt(per_hour_rate)}/hr",
                "amount": base_amount,
            }
        )
        if extra_hour_charges:
            breakdown.append(
                {
                    "label": _("Extra hours"),
                    "value": f"{_fmt(actual_hours - min_hours)} hrs × {symbol}{_fmt(per_hour_rate)}/hr",
                    "amount": extra_hour_charges,
                }
            )
        if extra_km_charges:
            breakdown.append(
                {
                    "label": _("Extra km"),
                    "value": f"{_fmt(driven_km - min_km)} km × {symbol}{_fmt(per_km_rate)}/km",
                    "amount": extra_km_charges,
                }
            )
        note = _(
            "Includes {0} hrs and {1} km. Extra hours are billed at {2}{3}/hr and extra km at {2}{4}/km on actuals."
        ).format(_fmt(min_hours), _fmt(min_km), symbol, _fmt(per_hour_rate), _fmt(per_km_rate))

    elif booking_type == "Outstation":
        if not pickup or not return_dt:
            frappe.throw(
                _("Pickup and return date/time are required for {0} bookings.").format(meta["label"]),
                frappe.ValidationError,
            )
        if return_dt <= pickup:
            frappe.throw(_("Return date/time must be after the pickup date/time."), frappe.ValidationError)
        hours = _hours_between(pickup, return_dt)
        days = _days_for(hours)
        nights = days - 1
        per_km_rate = rate("per_km_rate", "per_km_rate")
        night_rate = rate("night_rate", "night_surcharge") or policy["default_night_charge"]
        min_km_per_day = (
            rate("minimum_km_per_day", "minimum_km_per_day") or policy["default_min_km_per_day"]
        )
        round_trip = trip_type == "RoundTrip"
        leg_factor = 2 if round_trip else 1
        dead_km = flt(office_to_pickup_km) * (policy["dead_km_multiplier"] if round_trip else 1)
        route_km = flt(estimated_distance_km) * leg_factor
        travelled_km = driven_km if driven_km > 0 else route_km
        floor_km = min_km_per_day * days
        chargeable_km = int(round(max(travelled_km + dead_km, floor_km)))
        base_amount = flt(chargeable_km * per_km_rate, 2)
        night_charges = flt(nights * night_rate, 2)
        fare.update(
            days=days,
            nights=nights,
            chargeable_km=chargeable_km,
            min_km=chargeable_km,
            per_km_rate=per_km_rate,
            night_rate=night_rate,
            base_amount=base_amount,
            night_charges=night_charges,
            dead_km=flt(dead_km, 1),
            route_km=flt(route_km, 1),
            actual_hours=flt(hours, 2),
        )
        breakdown.append(
            {"label": _("Duration"), "value": f"{days} day(s), {nights} night(s)"}
        )
        if route_km:
            breakdown.append(
                {
                    "label": _("Route distance"),
                    "value": f"{_fmt(route_km)} km" + (" (round trip)" if round_trip else " (one way)"),
                }
            )
        if driven_km > 0:
            breakdown.append({"label": _("Logged distance"), "value": f"{_fmt(driven_km)} km"})
        if dead_km:
            breakdown.append({"label": _("Dispatch distance (office to pickup)"), "value": f"{_fmt(dead_km)} km"})
        breakdown.append(
            {"label": _("Minimum billable distance"), "value": f"{_fmt(min_km_per_day)} km/day × {days} = {_fmt(floor_km)} km"}
        )
        breakdown.append(
            {
                "label": _("Distance charge"),
                "value": f"{chargeable_km} km × {symbol}{_fmt(per_km_rate)}/km",
                "amount": base_amount,
            }
        )
        if night_charges:
            breakdown.append(
                {
                    "label": _("Night charges"),
                    "value": f"{nights} night(s) × {symbol}{_fmt(night_rate)}",
                    "amount": night_charges,
                }
            )
        note = _(
            "Billed on the higher of the trip distance (including dispatch km) and the {0} km/day minimum "
            "({1} km for {2} day(s)) at {3}{4}/km, plus {3}{5} per night. The fare is recalculated on the "
            "logged trip km."
        ).format(_fmt(min_km_per_day), _fmt(floor_km), days, symbol, _fmt(per_km_rate), _fmt(night_rate))

    else:
        # Package: the vendor enters grand_total; nothing is derived here.
        fare["actual_hours"] = flt(_hours_between(pickup, return_dt), 2)
        note = _("The price for this booking is set by the vendor.")
        fare.update(
            taxable=0.0,
            tax_total=0.0,
            grand_total=0.0,
            extra_fare_note=note,
            breakdown=[],
            taxes=[],
            booking_type=booking_type,
            trip_type=trip_type,
        )
        return fare

    subtotal = flt(fare["base_amount"] + fare["extra_hour_charges"] + fare["extra_km_charges"] + fare["night_charges"], 2)
    taxable = subtotal
    if apply_tax:
        rows = tax_target if tax_target is not None else []
        tax_total = apply_taxes(rows, taxable, policy)
        tax_rows = rows.get("tax_and_charges") if not isinstance(rows, list) else rows
        taxes = [
            {
                "label": cstr(_row_get(r, "remark")) or cstr(_row_get(r, "apply_on")),
                "rate": flt(_row_get(r, "rate")),
                "amount": flt(_row_get(r, "amount"), 2),
            }
            for r in tax_rows
        ]
    else:
        # Vendor cost is a pre-tax figure; we do not compute the vendor's GST.
        tax_total = 0.0
        taxes = []
    for t in taxes:
        breakdown.append(
            {
                "label": t["label"],
                "value": f"{_fmt(t['rate'])}%" if t["rate"] else "",
                "amount": t["amount"],
            }
        )
    grand_total = flt(taxable + tax_total, 2)
    breakdown.append({"label": _("Total"), "value": "", "amount": grand_total})
    fare.update(
        booking_type=booking_type,
        trip_type=trip_type,
        subtotal=subtotal,
        taxable=taxable,
        tax_total=tax_total,
        grand_total=grand_total,
        extra_fare_note=note,
        breakdown=breakdown,
        taxes=taxes,
    )
    return fare


# ── Vendor cost & margin ────────────────────────────────────────────────────────
# Amount fields on `Bookings` that `compute_vendor_cost` owns.
VENDOR_AMOUNT_FIELDS = (
    "vendor_base_amount",
    "vendor_night_charges",
    "vendor_extra_km_charges",
    "vendor_extra_hour_charges",
    "vendor_payable",
)

RATE_SOURCE_RATE_CARD = "Rate Card"
RATE_SOURCE_COMMISSION = "Commission"
RATE_SOURCE_MANUAL = "Manual"
RATE_SOURCE_UNSET = "Unset"


def _rate_card_rows(vendor):
    """Rate-card rows for a vendor, newest-first ties broken by row order."""
    if not vendor:
        return []
    return frappe.get_all(
        "Vendor Rate",
        filters={"parent": vendor, "parenttype": "Vendors"},
        fields=[
            "booking_type",
            "car_category",
            "car_model",
            "per_km_rate",
            "minimum_km_per_day",
            "night_charge",
            "per_hour_rate",
            "local_km_rate",
            "package",
            "package_amount",
        ],
        order_by="idx asc",
    )


def match_vendor_rate(vendor, booking_type, car_model=None, package=None):
    """Most specific matching rate-card row, or ``None``.

    Precedence (contract §2a): booking type + car model, then booking type + car category,
    then booking type with neither, i.e. a catch-all for that product.
    """
    rows = [r for r in _rate_card_rows(vendor) if r.get("booking_type") == booking_type]
    if not rows:
        return None

    category = (
        frappe.db.get_value("Car Models", car_model, "category") if car_model else None
    )

    def pick(predicate):
        for row in rows:
            if predicate(row):
                return row
        return None

    # A package-specific row is the most specific thing there is for a Local booking.
    if package:
        row = pick(lambda r: r.get("package") == package)
        if row:
            return row

    return (
        pick(lambda r: r.get("car_model") and r["car_model"] == car_model)
        or pick(lambda r: not r.get("car_model") and r.get("car_category") and r["car_category"] == category)
        or pick(lambda r: not r.get("car_model") and not r.get("car_category"))
    )


def _empty_vendor_cost():
    return {
        "vendor_rate_source": RATE_SOURCE_UNSET,
        "vendor_per_km_rate": 0.0,
        "vendor_per_hour_rate": 0.0,
        "vendor_night_charge": 0.0,
        "vendor_minimum_km_per_day": 0.0,
        "vendor_base_amount": 0.0,
        "vendor_night_charges": 0.0,
        "vendor_extra_km_charges": 0.0,
        "vendor_extra_hour_charges": 0.0,
        "vendor_payable": 0.0,
        "margin_amount": 0.0,
        "margin_percent": 0.0,
    }


def compute_vendor_cost(doc, policy=None):
    """What we owe the vendor for ``doc``, and the margin we keep.

    The trip geometry comes from the one fare engine; only the rates differ. When the vendor
    has no matching rate-card row we fall back to the vendor's flat commission, and failing
    that we report ``Unset`` with a zero cost — never a cost equal to the customer fare,
    which would silently imply zero margin.

    Margin is measured against the customer's PRE-TAX subtotal so GST cannot inflate it.
    """
    policy = policy or get_policy()
    out = _empty_vendor_cost()

    vendor = doc.get("assigned_to")
    booking_type = doc.get("booking_type")
    subtotal = flt(doc.get("base_amount")) + flt(doc.get("night_charges"))
    subtotal += flt(doc.get("extra_hour_charges")) + flt(doc.get("extra_km_charges"))
    subtotal = flt(subtotal, 2)

    if not vendor or booking_type == "Package":
        return out

    package_name = doc.get("package_type") if booking_type == "Local" else None
    row = match_vendor_rate(vendor, booking_type, doc.get("car_model"), package_name)
    manual = bool(doc.get("override_vendor_rates"))

    if manual:
        out["vendor_rate_source"] = RATE_SOURCE_MANUAL
        rates = {
            "per_km_rate": doc.get("vendor_per_km_rate"),
            "per_hour_rate": doc.get("vendor_per_hour_rate"),
            "night_rate": doc.get("vendor_night_charge"),
            "minimum_km_per_day": doc.get("vendor_minimum_km_per_day"),
        }
    elif row:
        out["vendor_rate_source"] = RATE_SOURCE_RATE_CARD
        # A flat package cost short-circuits the fare geometry entirely.
        if package_name and row.get("package") == package_name and flt(row.get("package_amount")):
            payable = flt(row["package_amount"], 2)
            out.update(
                vendor_base_amount=payable,
                vendor_payable=payable,
                margin_amount=flt(subtotal - payable, 2),
                margin_percent=flt((subtotal - payable) / subtotal * 100, 2) if subtotal else 0.0,
            )
            return out
        rates = {
            "per_km_rate": row.get("per_km_rate"),
            "per_hour_rate": row.get("per_hour_rate"),
            "night_rate": row.get("night_charge"),
            "minimum_km_per_day": row.get("minimum_km_per_day"),
            "local_km_rate": row.get("local_km_rate"),
        }
        if booking_type == "Local" and row.get("local_km_rate"):
            rates["per_km_rate"] = row["local_km_rate"]
    else:
        commission = flt(frappe.db.get_value("Vendors", vendor, "applicable_commission"))
        if commission <= 0:
            return out
        payable = flt(subtotal * (1 - commission / 100.0), 2)
        out.update(
            vendor_rate_source=RATE_SOURCE_COMMISSION,
            vendor_base_amount=payable,
            vendor_payable=payable,
            margin_amount=flt(subtotal - payable, 2),
            margin_percent=flt(commission, 2),
        )
        return out

    if not any(flt(v) for v in rates.values()):
        out["vendor_rate_source"] = RATE_SOURCE_MANUAL if manual else RATE_SOURCE_UNSET
        return out

    cost = compute_fare(
        booking_type=booking_type,
        car=get_car_rates(doc.get("car_model")),
        package=get_package(doc.get("package_type")) if booking_type == "Local" else None,
        pickup=doc.get("pickup_datetime"),
        return_dt=doc.get("return_datetime"),
        trip_type=doc.get("trip_type"),
        estimated_distance_km=doc.get("estimated_distance_km"),
        office_to_pickup_km=doc.get("office_to_pickup_km"),
        start_km=doc.get("start_km"),
        end_km=doc.get("end_km"),
        policy=policy,
        tax_target=None,
        rates=rates,
        apply_tax=False,
    )

    payable = flt(cost["subtotal"], 2)
    out.update(
        vendor_per_km_rate=flt(cost["per_km_rate"], 2),
        vendor_per_hour_rate=flt(cost["per_hour_rate"], 2),
        vendor_night_charge=flt(cost["night_rate"], 2),
        vendor_minimum_km_per_day=flt(rates.get("minimum_km_per_day") or 0, 2),
        vendor_base_amount=flt(cost["base_amount"], 2),
        vendor_night_charges=flt(cost["night_charges"], 2),
        vendor_extra_km_charges=flt(cost["extra_km_charges"], 2),
        vendor_extra_hour_charges=flt(cost["extra_hour_charges"], 2),
        vendor_payable=payable,
        margin_amount=flt(subtotal - payable, 2),
        margin_percent=flt((subtotal - payable) / subtotal * 100, 2) if subtotal else 0.0,
    )
    return out


# ── Settlement ──────────────────────────────────────────────────────────────────
def settlement_status(grand_total, customer_paid, vendor_payable, vendor_paid):
    """`Unsettled` / `Partially Settled` / `Settled` for a booking's two-sided money."""
    expected = flt(grand_total) + flt(vendor_payable)
    received = flt(customer_paid) + flt(vendor_paid)
    if received <= 0:
        return "Unsettled"
    customer_done = flt(customer_paid) >= flt(grand_total) - 0.01
    vendor_done = flt(vendor_paid) >= flt(vendor_payable) - 0.01
    if customer_done and vendor_done and expected > 0:
        return "Settled"
    return "Partially Settled"


def _paid_total(booking, direction):
    rows = frappe.get_all(
        "Payments",
        filters={"booking": booking, "payment_direction": direction, "docstatus": 1},
        fields=["amount"],
    )
    return flt(sum(flt(r["amount"]) for r in rows), 2)


def refresh_booking_settlement(booking):
    """Recompute a booking's paid/outstanding totals from its submitted `Payments`.

    Uses ``db_set`` so it neither re-runs booking validation nor recurses back into the
    `Payments` controller that called it.
    """
    if not booking or not frappe.db.exists("Bookings", booking):
        return

    customer_paid = _paid_total(booking, "Inbound")
    vendor_paid = _paid_total(booking, "Outbound")
    grand_total, vendor_payable = frappe.db.get_value(
        "Bookings", booking, ["grand_total", "vendor_payable"]
    )

    doc = frappe.get_doc("Bookings", booking)
    doc.db_set(
        {
            "customer_paid": customer_paid,
            "vendor_paid": vendor_paid,
            "customer_outstanding": flt(flt(grand_total) - customer_paid, 2),
            "vendor_outstanding": flt(flt(vendor_payable) - vendor_paid, 2),
            "settlement_status": settlement_status(
                grand_total, customer_paid, vendor_payable, vendor_paid
            ),
        },
        update_modified=False,
    )
