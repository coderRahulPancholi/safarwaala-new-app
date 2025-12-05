import frappe

def set_perm(doctype, role, perm_config):
    # perm_config is dict like {'read': 1, 'write': 0, 'create': 0}
    if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role}):
        d = frappe.new_doc("Custom DocPerm")
        d.parent = doctype
        d.role = role
        for key, val in perm_config.items():
            setattr(d, key, val)
        d.insert(ignore_permissions=True)
        print(f"Set Custom DocPerm for {doctype} - {role}")
    else:
        # Update existing
        name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role}, "name")
        d = frappe.get_doc("Custom DocPerm", name)
        for key, val in perm_config.items():
            setattr(d, key, val)
        d.save(ignore_permissions=True)
        print(f"Updated Custom DocPerm for {doctype} - {role}")

def run():
    # 1. Vendor Permissions
    # Vendors should manage their Cars and Drivers, and View Bookings
    set_perm("Cars", "Vendor", {'read': 1, 'write': 1, 'create': 1, 'delete': 1})
    set_perm("Drivers", "Vendor", {'read': 1, 'write': 1, 'create': 1, 'delete': 1})
    set_perm("Vendors", "Vendor", {'read': 1, 'write': 1}) # Manage own profile
    set_perm("OutStation Bookings", "Vendor", {'read': 1, 'write': 1}) # Assign driver/car
    set_perm("Duty Slips", "Vendor", {'read': 1})
    set_perm("Car Modals", "Vendor", {'read': 1}) # View modals

    # 2. Driver Permissions
    # Drivers view their assigned bookings and duty slips
    set_perm("Drivers", "Driver", {'read': 1, 'write': 1}) # Manage own profile
    set_perm("OutStation Bookings", "Driver", {'read': 1})
    set_perm("Duty Slips", "Driver", {'read': 1, 'write': 1}) # Update duty slip details? Assuming yes.

    # 3. Customer Permissions
    # Customers create/view bookings
    set_perm("Customer", "Customer", {'read': 1, 'write': 1}) # Manage own profile
    set_perm("OutStation Bookings", "Customer", {'read': 1, 'write': 1, 'create': 1}) 
    set_perm("City Master", "Customer", {'read': 1})
    set_perm("Car Modals", "Customer", {'read': 1})
    
    frappe.db.commit()
    print("Permissions assigned.")
