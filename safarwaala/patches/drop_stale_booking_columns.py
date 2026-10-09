# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Drop `Bookings` columns whose fields no longer exist.

`bench migrate` adds and alters columns but never removes one, so a field deleted from the
DocType JSON leaves its column (and its data) behind forever. These six are leftovers from
features that were removed:

* `expense_total`, `billable_expense_total`, `driver_expense_total` — the expense/driver-money
  tracking that went away with `Payouts` (the vendor pays its own drivers).
* `linked_invoice` — pointed at `Customer Invoice`, a DocType this app never shipped.
* `city_ride_package` — superseded by `package_type`.
* `trip_itinerary` — never populated by any code path.

A column is only dropped when it holds no data, so a surprise value is reported instead of
being destroyed.
"""

import frappe

DOCTYPE = "Bookings"
TABLE = "tabBookings"

STALE_COLUMNS = (
    "expense_total",
    "billable_expense_total",
    "driver_expense_total",
    "linked_invoice",
    "city_ride_package",
    "trip_itinerary",
)


def _columns():
    return {
        r[0]
        for r in frappe.db.sql(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = DATABASE() AND table_name = %s""",
            (TABLE,),
        )
    }


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    present = _columns()
    # Never drop a column the current DocType still declares.
    declared = {df.fieldname for df in frappe.get_meta(DOCTYPE).fields}

    for column in STALE_COLUMNS:
        if column not in present or column in declared:
            continue

        used = frappe.db.sql(
            f"SELECT COUNT(*) FROM `{TABLE}` WHERE `{column}` IS NOT NULL AND `{column}` != ''"
        )[0][0]
        if used:
            print(f"Kept {TABLE}.{column}: {used} row(s) hold data")
            continue

        frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` DROP COLUMN `{column}`")
        print(f"Dropped empty column {TABLE}.{column}")

    # Orphaned DocField rows for the same removed fields.
    removed = frappe.db.sql(
        """DELETE FROM `tabDocField`
           WHERE parent = %s AND fieldname IN %s""",
        (DOCTYPE, STALE_COLUMNS),
    )
    if removed:
        print(f"Removed stale DocField rows for {DOCTYPE}")

    frappe.clear_cache(doctype=DOCTYPE)
