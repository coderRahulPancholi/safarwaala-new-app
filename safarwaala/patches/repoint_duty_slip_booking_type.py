# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Repoint `Duty Slips.booking_type` at the surviving `Bookings` DocType.

`booking_type` is a Link to DocType and `booking_id` is a Dynamic Link that reads it.
When `OutStation Bookings` / `Local Bookings` / `Bookings Master` were consolidated into
`Bookings`, the rows kept the old DocType names as *data*.

`repoint_legacy_booking_doctypes` fixed the desk metadata (Number Cards, Workspace Links)
but not the document data, so every existing Duty Slip still pointed at a DocType that no
longer exists. Opening one raised `DocType Bookings Master not found` from
`set_link_titles()` — the whole form failed to load, for every slip and every role.

`api/booking.py:manage_duty_slip` already writes `booking_type = "Bookings"`, so this is
purely a backfill of rows created before the consolidation.

Note: the `booking_id` values of those legacy rows reference bookings that were never
migrated into `tabBookings`. A Dynamic Link pointing at a missing *document* is harmless —
the form renders with an unresolved link — whereas one pointing at a missing *DocType* is
fatal. The ids are deliberately left as-is: they are the only remaining record of which
booking each slip belonged to, and inventing a mapping would be worse than an empty link.
"""

import frappe

LEGACY_BOOKING_DOCTYPES = (
	"Bookings Master",
	"OutStation Bookings",
	"Local Bookings",
	"Routine Bookings",
)

CURRENT_BOOKING_DOCTYPE = "Bookings"


def execute():
	if not frappe.db.table_exists("Duty Slips"):
		return

	stale = frappe.db.get_all(
		"Duty Slips",
		filters={"booking_type": ("in", LEGACY_BOOKING_DOCTYPES)},
		fields=["name", "booking_type"],
	)
	if not stale:
		return

	frappe.db.sql(
		"""
		UPDATE `tabDuty Slips`
		SET `booking_type` = %s
		WHERE `booking_type` IN %s
		""",
		(CURRENT_BOOKING_DOCTYPE, LEGACY_BOOKING_DOCTYPES),
	)

	counts = {}
	for row in stale:
		counts[row["booking_type"]] = counts.get(row["booking_type"], 0) + 1
	for old, count in sorted(counts.items()):
		print(f"Duty Slips: {count} row(s) repointed {old} -> {CURRENT_BOOKING_DOCTYPE}")

	frappe.clear_cache(doctype="Duty Slips")
