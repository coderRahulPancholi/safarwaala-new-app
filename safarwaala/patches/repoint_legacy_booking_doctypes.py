# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Repoint desk metadata that still references removed booking DocTypes.

The app consolidated `OutStation Bookings` / `Local Bookings` / `Routine Bookings` /
`Bookings Master` into the single `Bookings` DocType, and driver payouts into `Payouts`.
The JSON definitions were updated, but Number Cards, Workspace Links and Workspace
Shortcuts are only created from JSON on *first* sync — existing rows keep the dead
`document_type` / `link_to`, which makes the Driver and Vendor workspaces raise
"DocType OutStation Bookings not found" when opened.

This patch rewrites those rows and drops the ones that have no valid replacement.
"""

import frappe

# Removed DocType -> replacement, or None to delete the referencing row.
DOCTYPE_MAP = {
    "OutStation Bookings": "Bookings",
    "Local Bookings": "Bookings",
    "Routine Bookings": "Bookings",
    "Bookings Master": "Bookings",
    # Driver payouts are gone entirely: the vendor pays its own drivers. Money movement
    # now lives in the single bidirectional `Payments` DocType.
    "Driver Payment": "Payments",
    "Payouts": "Payments",
    "Vehicle Expense Log": None,
    "Customer Invoice": None,
}


def _resolve(old):
    """Replacement DocType for `old`, or None when the row should be removed."""
    new = DOCTYPE_MAP.get(old)
    if not new or not frappe.db.exists("DocType", new):
        return None
    return new


def _drop_removed_doctypes():
    """Delete DocTypes whose definition no longer ships with the app.

    `bench migrate` never removes a DocType on its own, so `Payouts` would linger in the
    Desk (and in reports) after its directory was deleted.
    """
    for name in ("Payouts",):
        if not frappe.db.exists("DocType", name):
            continue
        rows = frappe.db.count(name)
        if rows:
            print(f"Kept DocType {name}: {rows} row(s) present, refusing to drop data")
            continue
        frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{name}`")
        print(f"Dropped empty DocType {name}")


def execute():
    _drop_removed_doctypes()

    # (doctype, field holding the DocType reference)
    targets = (
        ("Number Card", "document_type"),
        ("Workspace Link", "link_to"),
        ("Workspace Shortcut", "link_to"),
        ("Dashboard Chart", "document_type"),
    )

    for doctype, field in targets:
        if not frappe.db.exists("DocType", doctype):
            continue

        rows = frappe.get_all(
            doctype,
            filters={field: ("in", list(DOCTYPE_MAP))},
            fields=["name", field],
        )
        for row in rows:
            old = row.get(field)
            new = _resolve(old)
            if new:
                frappe.db.set_value(doctype, row["name"], field, new, update_modified=False)
                print(f"{doctype} {row['name']}: {field} {old} -> {new}")
            else:
                frappe.db.delete(doctype, {"name": row["name"]})
                print(f"{doctype} {row['name']}: removed (no replacement for {old})")

    # Number Card filters embed the DocType name inside the stored JSON string.
    if frappe.db.exists("DocType", "Number Card"):
        for card in frappe.get_all(
            "Number Card", fields=["name", "filters_json", "dynamic_filters_json"]
        ):
            for field in ("filters_json", "dynamic_filters_json"):
                value = card.get(field)
                if not value:
                    continue
                updated = value
                for old, new in DOCTYPE_MAP.items():
                    if new and old in updated:
                        updated = updated.replace(old, new)
                if updated != value:
                    frappe.db.set_value(
                        "Number Card", card["name"], field, updated, update_modified=False
                    )
                    print(f"Number Card {card['name']}: {field} rewritten")

    normalize_booking_permissions()
    frappe.clear_cache()


def normalize_booking_permissions():
    """Drop permission rows for removed DocTypes and de-duplicate the `Bookings` rows.

    Also registered as an ``after_migrate`` hook: ``frappe`` runs ``sync_fixtures()``
    *after* patches, which re-seeds the legacy rows from ``fixtures/custom_docperm.json``
    on sites installed before the consolidation. Running last makes the result stable.
    """
    if not frappe.db.exists("DocType", "Custom DocPerm"):
        return

    stale = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": ("in", list(DOCTYPE_MAP))},
        pluck="name",
    )
    for name in stale:
        frappe.db.delete("Custom DocPerm", {"name": name})
    if stale:
        print(f"Removed {len(stale)} Custom DocPerm rows for removed DocTypes")

    # Consolidating the legacy booking DocTypes onto `Bookings` can leave several rows
    # for the same role. Keep one per (role, permlevel), folding in every grant.
    FLAGS = (
        "read", "write", "create", "delete", "submit", "cancel", "amend",
        "report", "export", "import", "print", "email", "share", "select",
    )
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": "Bookings"},
        fields=["name", "role", "permlevel", "if_owner", *FLAGS],
        order_by="creation asc",
    )
    keep = {}
    merged = 0
    for row in rows:
        key = (row["role"], row["permlevel"])
        winner = keep.get(key)
        if winner is None:
            keep[key] = row
            continue
        for flag in FLAGS:
            if row[flag] and not winner[flag]:
                frappe.db.set_value(
                    "Custom DocPerm", winner["name"], flag, 1, update_modified=False
                )
                winner[flag] = 1
        # A row without `if_owner` is broader than one with it.
        if winner["if_owner"] and not row["if_owner"]:
            frappe.db.set_value(
                "Custom DocPerm", winner["name"], "if_owner", 0, update_modified=False
            )
            winner["if_owner"] = 0
        frappe.db.delete("Custom DocPerm", {"name": row["name"]})
        merged += 1

    if merged:
        print(f"Merged {merged} duplicate Bookings permission row(s)")

    frappe.clear_cache()
