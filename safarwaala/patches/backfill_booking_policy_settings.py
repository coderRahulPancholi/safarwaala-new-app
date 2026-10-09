# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Persist the booking-policy defaults onto the ``Safarwaala Settings`` Single.

Frappe only applies a DocField ``default`` when a document row is *created*. The
``Safarwaala Settings`` Single predates the booking-policy fields, so those fields have
no row in ``tabSingles`` at all. ``booking_policy.get_settings()`` papers over that by
falling back to the DocField default, but the moment anyone opens the Settings form and
saves it, Frappe writes the loaded (empty) values back — silently turning GST off and
zeroing ``min_advance_minutes``, ``default_min_km_per_day``, ``dead_km_multiplier`` and
``min_mobile_digits``.

This patch materialises the defaults so the stored state matches the intended policy and
a no-op save becomes harmless. Only fields that are genuinely absent are written, so an
operator's deliberate configuration is never overwritten.
"""

import frappe
from frappe.model import no_value_fields

SETTINGS_DOCTYPE = "Safarwaala Settings"

# Fields whose default must exist in the DB for fare calculation to behave correctly.
POLICY_FIELDS = (
    "currency",
    "currency_symbol",
    "default_booking_status",
    "apply_gst",
    "gst_percent",
    "gst_label",
    "enable_package_bookings",
    "min_advance_minutes",
    "max_advance_days",
    "min_mobile_digits",
    "default_min_km_per_day",
    "default_night_charge",
    "dead_km_multiplier",
    "local_radius_km",
    "outstation_trip_types",
    "avg_speed_kmph",
    "max_driving_hours_per_day",
    "min_rest_hours_at_destination",
    "feasibility_buffer_percent",
    "local_inclusions",
    "local_exclusions",
    "outstation_inclusions",
    "outstation_exclusions",
)


def execute():
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return

    meta = frappe.get_meta(SETTINGS_DOCTYPE)
    stored = frappe.db.get_singles_dict(SETTINGS_DOCTYPE)

    written = []
    for fieldname in POLICY_FIELDS:
        df = meta.get_field(fieldname)
        if not df or df.fieldtype in no_value_fields:
            continue
        if df.default in (None, ""):
            continue
        # Only backfill when the value is genuinely absent — never clobber real config.
        if stored.get(fieldname) not in (None, ""):
            continue
        frappe.db.set_single_value(SETTINGS_DOCTYPE, fieldname, df.default)
        written.append(f"{fieldname}={df.default}")

    if written:
        print(f"Backfilled {SETTINGS_DOCTYPE}: {', '.join(written)}")

    frappe.clear_cache()
    try:
        from safarwaala.safarwaala.booking_policy import clear_booking_cache

        clear_booking_cache()
    except Exception:
        pass
