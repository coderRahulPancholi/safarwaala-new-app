import frappe

def run():
    doctypes = ["Car Modals", "Cars", "File"]
    for dt in doctypes:
        # Check if Custom DocPerm exists for Guest
        # We need to add it to the permissions list of the Doctype if strictly using Custom DocPerm is not enough or proper way.
        # But 'Custom DocPerm' is for overriding. 
        # Actually, adding a row to the 'permissions' child table of the DocType is the standard way, 
        # OR using Custom DocPerm if we don't want to modify the source JSON.
        # Since I'm in development on a local bench, modifying the DocType directly is fine and better for persistence if I export fixtures.
        # However, purely for "enabling public access now", Custom DocPerm is safer to avoid git changes if not intended.
        # Let's try to add via Custom DocPerm first.
        
        if not frappe.db.exists("Custom DocPerm", {"parent": dt, "role": "Guest", "read": 1}):
            d = frappe.new_doc("Custom DocPerm")
            d.parent = dt
            d.role = "Guest"
            d.read = 1
            d.write = 0
            d.create = 0
            d.submit = 0
            d.cancel = 0
            d.amend = 0
            d.report = 1
            d.export = 0
            d.import_ = 0
            d.share = 0
            d.print = 0
            d.email = 0
            d.insert(ignore_permissions=True)
            print(f"Added Guest Read permission for {dt}")
        else:
            print(f"Guest Read permission already exists for {dt}")
    
    frappe.db.commit()
