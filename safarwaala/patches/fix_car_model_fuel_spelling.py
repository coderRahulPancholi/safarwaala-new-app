# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Correct the `Car Models.fuel_type` spelling `Deisel` -> `Diesel`.

Runs in `post_model_sync` because it needs healthy DocType meta: `Car Models.autoname` is
`format:{model_name}-({fuel_type})`, so the fuel value is part of the document name.
Renaming it therefore renames the document, and `frappe.rename_doc` is what rewrites every
inbound link (`Cars.car_model`, `Bookings.car_model`, `Duty Slips.car_model`, `Lead.car_model`).

The column/DocType renames happen earlier, in the `pre_model_sync` patch
`rename_car_models_and_fields`.
"""

import frappe
from frappe.model.rename_doc import rename_doc

DOCTYPE = "Car Models"
FUEL_FIXES = {"Deisel": "Diesel"}


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    # Guard: the new column must exist before we derive names from it. If the
    # `pre_model_sync` rename did not land, `model_name` reads as NULL and every row would
    # collapse onto a single `None-(Diesel)` document, destroying the car models.
    columns = frappe.db.get_table_columns(DOCTYPE)
    if "model_name" not in columns:
        frappe.throw(
            f"{DOCTYPE}.model_name is missing — the pre_model_sync patch "
            "`rename_car_models_and_fields` has not applied. Aborting rather than "
            "renaming documents to a NULL-derived name."
        )

    for wrong, right in FUEL_FIXES.items():
        rows = frappe.get_all(
            DOCTYPE, filters={"fuel_type": wrong}, fields=["name", "model_name"]
        )
        for row in rows:
            if not row.get("model_name"):
                print(f"Skipped {row['name']}: blank model_name")
                continue

            frappe.db.set_value(DOCTYPE, row["name"], "fuel_type", right, update_modified=False)

            new_name = f"{row['model_name']}-({right})"
            if row["name"] == new_name:
                continue
            if frappe.db.exists(DOCTYPE, new_name):
                print(f"Skipped {row['name']}: {new_name} already exists")
                continue

            rename_doc(
                DOCTYPE,
                row["name"],
                new_name,
                force=True,
                ignore_permissions=True,
                show_alert=False,
            )
            print(f"Renamed {row['name']} -> {new_name}")

    frappe.clear_cache()
