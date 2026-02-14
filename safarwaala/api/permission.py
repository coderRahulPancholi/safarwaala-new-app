import frappe

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
    return f"`linked_user` = '{user}'"

def has_linked_permission(doc, user):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    if doc.get("linked_user") == user:
        return True

    return False

def get_outstation_booking_condition(user):
    if not user:
        user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return ""

    conditions = []

    # Vendor Check: specific to 'assigned_to'
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor:
            conditions.append(f"`assigned_to` = '{vendor}'")
    
    # Driver Check: specific to 'driver'
    if "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver:
            conditions.append(f"`driver` = '{driver}'")

    # Customer Check: specific to 'customer'
    if "Customer" in frappe.get_roles(user):
        customer = frappe.db.get_value("Customer", {"linked_user": user}, "name")
        if customer:
            conditions.append(f"`customer` = '{customer}'")

    if not conditions:
        return "1=0" # Access denied if no role/link matches
        
    return "(" + " OR ".join(conditions) + ")"

def has_outstation_booking_permission(doc, user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return True

    allow = False

    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor and doc.assigned_to == vendor:
            allow = True
    
    if not allow and "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver and doc.driver == driver:
            allow = True

    if not allow and "Customer" in frappe.get_roles(user):
        customer = frappe.db.get_value("Customer", {"linked_user": user}, "name")
        if customer and doc.customer == customer:
            allow = True

    return allow

def get_duty_slip_condition(user):
    if not user:
         user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return ""
        
    # Assuming Duty Slips acts similarly or mainly for Drivers
    # If Vendor also needs to see Duty Slips of their drivers, we'd need to join. 
    # For now, implemented for Driver as requested.
    
    if "Driver" in frappe.get_roles(user):
         driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
         if driver:
             return f"`driver` = '{driver}'"
    
    return "1=0"

def has_duty_slip_permission(doc, user):
     if not user:
        user = frappe.session.user

     if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return True
        
     if "Driver" in frappe.get_roles(user):
         driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
         if driver and doc.driver == driver:
             return True
             
     return False

def get_driver_condition(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return ""

    conditions = []
    
    # Driver sees themselves
    conditions.append(f"`linked_user` = '{user}'")
    
    # Vendor sees their drivers
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor:
            conditions.append(f"`owner_vendor` = '{vendor}'")

    return "(" + " OR ".join(conditions) + ")"

def has_driver_permission(doc, user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return True

    # Driver Access
    if doc.get("linked_user") == user:
        return True

    # Vendor Access
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor and doc.get("owner_vendor") == vendor:
            return True

    return False

def get_driver_payment_condition(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return ""

    conditions = []
    
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor:
            conditions.append(f"`vendor` = '{vendor}'")

    if "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver:
            conditions.append(f"`driver` = '{driver}'")

    if not conditions:
        return "1=0"
        
    return "(" + " OR ".join(conditions) + ")"

def has_driver_payment_permission(doc, user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return True

    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor and doc.vendor == vendor:
            return True
            
    if "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver and doc.driver == driver:
            return True

    return False


def get_bookings_master_condition(user):
    if not user:
        user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return ""

    conditions = []

    # Vendor Check: specific to 'assigned_to'
    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor:
            conditions.append(f"`assigned_to` = '{vendor}'")
    
    # Driver Check: specific to 'driver'
    if "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver:
            conditions.append(f"`driver` = '{driver}'")

    # Customer Check: specific to 'customer'
    if "Customer" in frappe.get_roles(user):
        customer = frappe.db.get_value("Customer", {"linked_user": user}, "name")
        if customer:
            conditions.append(f"`customer` = '{customer}'")

    if not conditions:
        return "1=0"
        
    return "(" + " OR ".join(conditions) + ")"

def has_bookings_master_permission(doc, user=None, permission_type=None):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
        return True
    
    # Allow creation if standard role permissions pass
    if doc.is_new() or permission_type == "create":
        return True

    allow = False

    if "Vendor" in frappe.get_roles(user):
        vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
        if vendor and doc.assigned_to == vendor:
            allow = True
    
    if not allow and "Driver" in frappe.get_roles(user):
        driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
        if driver and doc.driver == driver:
            allow = True

    if not allow and "Customer" in frappe.get_roles(user):
        customer = frappe.db.get_value("Customer", {"linked_user": user}, "name")
        if customer and doc.customer == customer:
            allow = True

    return allow
