# Copyright (c) 2026, rahul and contributors
# For license information, please see license.txt

"""Rename the `Car Modals` DocType to `Car Models` and fix the misspelled field names.

Runs in `pre_model_sync`, i.e. *before* Frappe syncs the DocType JSON into the database.
The JSON definitions already carry the new names, so without this patch `bench migrate`
would add brand-new empty columns and orphan the live data (41 `Cars` rows, 6 car models).

Everything here is deliberately **raw SQL**. The higher-level helpers
(`frappe.rename_doc`, `rename_field`) load DocType meta, and at this point the meta on disk
(new names) disagrees with the database (old names) — using them raises
`Unknown column 'model_name'`. Document-level work that needs healthy meta happens in the
companion `post_model_sync` patch `fix_car_model_fuel_spelling`.
"""

import frappe

OLD_DOCTYPE = "Car Modals"
NEW_DOCTYPE = "Car Models"

# (doctype, old fieldname, new fieldname)
FIELD_RENAMES = (
    (NEW_DOCTYPE, "modal_name", "model_name"),
    ("Cars", "modal", "car_model"),
    ("Duty Slips", "car_modal", "car_model"),
    ("Duty Slips", "from", "from_location"),
    ("Duty Slips", "to", "to_location"),
    ("Lead", "car_modal", "car_model"),
    ("Customer", "name1", "full_name"),
    ("Drivers", "name1", "full_name"),
)

# Link/Dynamic-Link option values and fetch_from paths that embed the old names.
META_SUBS = (
    ("options", OLD_DOCTYPE, NEW_DOCTYPE),
    ("fetch_from", "customer.name1", "customer.full_name"),
    ("fetch_from", "driver.name1", "driver.full_name"),
    ("fetch_from", "car_model.modal_name", "car_model.model_name"),
    ("fetch_from", "booking_id.assigned_to", "booking_id.assigned_to"),
)


def _table_exists(table):
    """Direct schema lookup.

    ``frappe.db.table_exists`` is cache-backed and returns stale answers in the middle of a
    migration, which silently skips every rename below.
    """
    return bool(
        frappe.db.sql(
            """SELECT 1 FROM information_schema.tables
               WHERE table_schema = DATABASE() AND table_name = %s""",
            (table,),
        )
    )


def _columns(table):
    return {
        r[0]
        for r in frappe.db.sql(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = DATABASE() AND table_name = %s""",
            (table,),
        )
    }


def _column_type(table, column):
    row = frappe.db.sql(
        """SELECT column_type, is_nullable, column_default FROM information_schema.columns
           WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s""",
        (table, column),
    )
    return row[0] if row else None


def execute():
    # ── 1. Rename the physical table ────────────────────────────────────────────
    old_table, new_table = f"tab{OLD_DOCTYPE}", f"tab{NEW_DOCTYPE}"
    if _table_exists(old_table) and not _table_exists(new_table):
        frappe.db.sql_ddl(f"RENAME TABLE `{old_table}` TO `{new_table}`")
        print(f"Renamed table {old_table} -> {new_table}")

    # ── 2. Rename columns FIRST ─────────────────────────────────────────────────
    # Must precede the DocType row rename. `FIELD_RENAMES` is keyed on the NEW DocType
    # name, and the table above is already renamed, so the columns can be moved now.
    # Doing the DocType row first would leave this loop looking at a table whose
    # DocField rows still say `Car Modals`, silently skipping every column rename and
    # leaving `model_name` absent — which then reads as NULL and collapses the autoname.
    for doctype, old, new in FIELD_RENAMES:
        table = f"tab{doctype}"
        cols = _columns(table)
        if old in cols and new not in cols:
            spec = _column_type(table, old)
            if not spec:
                continue
            col_type, nullable, default = spec
            clause = f"`{new}` {col_type}"
            clause += " NULL" if nullable == "YES" else " NOT NULL"
            if default is not None:
                clause += f" DEFAULT {frappe.db.escape(default)}"
            frappe.db.sql_ddl(f"ALTER TABLE `{table}` CHANGE `{old}` {clause}")
            print(f"Renamed column {table}.{old} -> {new}")

        # The DocField row must follow the column. Match on either DocType name so this
        # self-heals if a previous run renamed the DocType row but not the columns.
        if _table_exists("tabDocField"):
            frappe.db.sql(
                """UPDATE `tabDocField` SET fieldname = %s
                   WHERE parent IN (%s, %s) AND fieldname = %s""",
                (new, doctype, OLD_DOCTYPE if doctype == NEW_DOCTYPE else doctype, old),
            )

    # ── 3. Rename the DocType row and its child metadata ────────────────────────
    if frappe.db.exists("DocType", OLD_DOCTYPE) and not frappe.db.exists("DocType", NEW_DOCTYPE):
        frappe.db.sql("UPDATE `tabDocType` SET name = %s WHERE name = %s", (NEW_DOCTYPE, OLD_DOCTYPE))
        print(f"Renamed DocType {OLD_DOCTYPE} -> {NEW_DOCTYPE}")
    for table, column in (
        ("tabDocField", "parent"),
        ("tabDocPerm", "parent"),
        ("tabCustom DocPerm", "parent"),
        ("tabDocType Link", "parent"),
        ("tabDocType Action", "parent"),
    ):
        if _table_exists(table):
            frappe.db.sql(
                f"UPDATE `{table}` SET `{column}` = %s WHERE `{column}` = %s",
                (NEW_DOCTYPE, OLD_DOCTYPE),
            )

    # Autoname expression lives on the DocType row itself.
    frappe.db.sql(
        "UPDATE `tabDocType` SET autoname = %s WHERE name = %s",
        ("format:{model_name}-({fuel_type})", NEW_DOCTYPE),
    )

    # ── 4. Settings Single: values are rows in tabSingles, not columns ──────────
    frappe.db.sql(
        "DELETE FROM `tabSingles` WHERE doctype = 'Safarwaala Settings' AND field = %s",
        ("platform_commission",),
    )
    frappe.db.sql(
        "UPDATE `tabSingles` SET field = %s WHERE doctype = 'Safarwaala Settings' AND field = %s",
        ("platform_commission", "platform_commision"),
    )
    frappe.db.sql(
        "UPDATE `tabDocField` SET fieldname = %s WHERE parent = 'Safarwaala Settings' AND fieldname = %s",
        ("platform_commission", "platform_commision"),
    )
    frappe.db.sql(
        "UPDATE `tabDocField` SET fieldname = %s WHERE parent = 'Safarwaala Settings' AND fieldname = %s",
        ("office_details_tab", "office_deatils_tab"),
    )

    # ── 5. Repoint link options and fetch_from paths ────────────────────────────
    for column, old, new in META_SUBS:
        if old == new:
            continue
        frappe.db.sql(
            f"UPDATE `tabDocField` SET `{column}` = %s WHERE `{column}` = %s", (new, old)
        )
    for table in ("tabCustom Field", "tabProperty Setter"):
        if _table_exists(table):
            col = "options" if table == "tabCustom Field" else "value"
            frappe.db.sql(
                f"UPDATE `{table}` SET `{col}` = %s WHERE `{col}` = %s",
                (NEW_DOCTYPE, OLD_DOCTYPE),
            )

    # Dynamic Link rows that store the DocType name as data.
    for table, column in (
        ("tabDuty Slips", "booking_type"),
        ("tabPayments", "record_type"),
    ):
        if _table_exists(table) and column in _columns(table):
            frappe.db.sql(
                f"UPDATE `{table}` SET `{column}` = %s WHERE `{column}` = %s",
                (NEW_DOCTYPE, OLD_DOCTYPE),
            )

    frappe.clear_cache()
