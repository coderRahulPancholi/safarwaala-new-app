import frappe
from safarwaala.safarwaala.report.driver_ledger.driver_ledger import get_data as get_ledger_data

@frappe.whitelist()
def get_driver_pending_balance(filters=None):
    user = frappe.session.user
    if user == "Administrator":
        return 0
    
    total_balance = 0
    
    # Check if Vendor
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor:
            # Get all drivers for this vendor
            drivers = frappe.get_all("Drivers", filters={"owner_vendor": vendor}, pluck="name")
            for driver in drivers:
                data = get_ledger_data(frappe._dict({"driver": driver}))
                if data:
                    total_balance += (data[-1].get("balance") or 0)
        return total_balance

    # Check if Driver
    driver_name = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
    if driver_name:
        data = get_ledger_data(frappe._dict({"driver": driver_name}))
        if data:
            return data[-1].get("balance") or 0
            
    return 0
