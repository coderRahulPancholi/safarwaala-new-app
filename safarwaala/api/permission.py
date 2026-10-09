import frappe
from frappe.utils import cstr

# ── Helpers ─────────────────────────────────────────────────────────────────────
def _is_admin(user):
    roles = frappe.get_roles(user)
    return user == "Administrator" or "System Manager" in roles


def _linked_name(doctype, user):
    return frappe.db.get_value(doctype, {"linked_user": user}, "name")


def _eq(fieldname, value):
    """Escaped ``fieldname = value`` SQL condition."""
    return f"`{fieldname}` = {frappe.db.escape(value)}"


# ── Customer / Drivers / Vendors ────────────────────────────────────────────────
def get_linked_user_condition(user):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""
    if "System Manager" in frappe.get_roles(user):
        return ""
    if "Vendor" in frappe.get_roles(user):
        return ""

    # Applies to Customer, Drivers, Vendors where the field is 'linked_user'
    return _eq("linked_user", user)

def has_linked_permission(doc, user):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    if doc.get("linked_user") == user:
        return True

    return False

def get_driver_condition(user):
    if not user:
        user = frappe.session.user

    if _is_admin(user):
        return ""

    conditions = []

    # Driver sees themselves
    conditions.append(_eq("linked_user", user))

    # Vendor sees their drivers
    if "Vendor" in frappe.get_roles(user):
        vendor = _linked_name("Vendors", user)
        if vendor:
            conditions.append(_eq("owner_vendor", vendor))

    return "(" + " OR ".join(conditions) + ")"

def has_driver_permission(doc, user):
    if not user:
        user = frappe.session.user

    if _is_admin(user):
        return True

    # Driver Access
    if doc.get("linked_user") == user:
        return True

    # Vendor Access
    if "Vendor" in frappe.get_roles(user):
        vendor = _linked_name("Vendors", user)
        if vendor and doc.get("owner_vendor") == vendor:
            return True

    return False


# ── Bookings ────────────────────────────────────────────────────────────────────
def get_booking_party_links(user):
    """The session user's linked party records as ``{fieldname_on_bookings: name}``."""
    links = {}
    vendor = _linked_name("Vendors", user)
    if vendor:
        links["assigned_to"] = vendor
    driver = _linked_name("Drivers", user)
    if driver:
        links["driver"] = driver
    customer = _linked_name("Customer", user)
    if customer:
        links["customer"] = customer
    return links

# Internal commercials on `Bookings`. Frappe enforces `permlevel` when *returning* fields,
# but `frappe.db.get_list` happily accepts them in `filters` and `order_by`, which leaks the
# values by inference (e.g. sort by margin, or filter `margin_amount > x`). The query
# condition below runs on every list read, so it is the one place that sees every such
# request and can refuse it.
VENDOR_ONLY_BOOKING_FIELDS = (
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
)


def _block_vendor_field_inference():
    """Refuse a list query that filters or sorts on an internal commercial field."""
    request = cstr(frappe.local.form_dict.get("filters")) + cstr(
        frappe.local.form_dict.get("order_by")
    ) + cstr(frappe.local.form_dict.get("group_by")) + cstr(
        frappe.local.form_dict.get("having")
    )
    if not request:
        return
    lowered = request.lower()
    for field in VENDOR_ONLY_BOOKING_FIELDS:
        if field in lowered:
            frappe.throw(
                frappe._("You are not permitted to query {0}.").format(field),
                frappe.PermissionError,
            )


def get_bookings_condition(user):
    if not user:
        user = frappe.session.user

    if _is_admin(user):
        return ""

    _block_vendor_field_inference()

    links = get_booking_party_links(user)
    if not links:
        return "1=0"

    return "(" + " OR ".join(_eq(field, name) for field, name in links.items()) + ")"

def has_bookings_permission(doc, user=None, ptype=None):
    if not user:
        user = frappe.session.user

    if _is_admin(user):
        return True

    # Creation is governed by the standard role permissions
    if doc.is_new() or ptype == "create":
        return True

    return any(doc.get(field) == name for field, name in get_booking_party_links(user).items())


# ── Duty Slips ──────────────────────────────────────────────────────────────────
def get_duty_slip_condition(user):
    if not user:
         user = frappe.session.user

    if _is_admin(user):
        return ""

    # Duty slips are visible to the driver they belong to.
    if "Driver" in frappe.get_roles(user):
         driver = _linked_name("Drivers", user)
         if driver:
             return _eq("driver", driver)

    return "1=0"

def has_duty_slip_permission(doc, user):
     if not user:
        user = frappe.session.user

     if _is_admin(user):
        return True

     if "Driver" in frappe.get_roles(user):
         driver = _linked_name("Drivers", user)
         if driver and doc.driver == driver:
             return True

     return False
