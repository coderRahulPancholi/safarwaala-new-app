# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Recompute the settlement roll-up on bookings that predate those fields.

`customer_paid` / `vendor_paid` and the outstanding amounts are maintained by the `Payments`
controller, and `Bookings.validate` derives the rest. Neither runs for a booking created
before the fields existed and never saved since, so those rows sit at 0 outstanding while
owing the full fare — the booking detail screen then shows "Total ₹9,434.25 / Balance due ₹0"
on an unsettled booking.

Uses `db_set` so submitted and cancelled bookings are corrected too, without re-running
validation (which would re-price them against today's rates).
"""

import frappe
from frappe.utils import flt

DOCTYPE = "Bookings"


def _paid(booking, direction):
    if not frappe.db.exists("DocType", "Payments"):
        return 0.0
    rows = frappe.get_all(
        "Payments",
        filters={"booking": booking, "payment_direction": direction, "docstatus": 1},
        pluck="amount",
    )
    return flt(sum(flt(a) for a in rows), 2)


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    from safarwaala.safarwaala.booking_policy import settlement_status

    fixed = 0
    for row in frappe.get_all(
        DOCTYPE,
        fields=["name", "grand_total", "vendor_payable", "customer_outstanding", "vendor_outstanding"],
    ):
        customer_paid = _paid(row.name, "Inbound")
        vendor_paid = _paid(row.name, "Outbound")
        customer_outstanding = flt(flt(row.grand_total) - customer_paid, 2)
        vendor_outstanding = flt(flt(row.vendor_payable) - vendor_paid, 2)

        if (
            abs(customer_outstanding - flt(row.customer_outstanding)) < 0.01
            and abs(vendor_outstanding - flt(row.vendor_outstanding)) < 0.01
        ):
            continue

        frappe.db.set_value(
            DOCTYPE,
            row.name,
            {
                "customer_paid": customer_paid,
                "vendor_paid": vendor_paid,
                "customer_outstanding": customer_outstanding,
                "vendor_outstanding": vendor_outstanding,
                "settlement_status": settlement_status(
                    row.grand_total, customer_paid, row.vendor_payable, vendor_paid
                ),
            },
            update_modified=False,
        )
        fixed += 1

    if fixed:
        print(f"Recomputed settlement totals on {fixed} booking(s)")
