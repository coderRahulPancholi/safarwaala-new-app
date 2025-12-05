import frappe
from frappe.utils import random_string

def create_role_if_not_exists(role_name):
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)
        print(f"Created Role: {role_name}")

def create_user_and_link(doctype, identifiers, role_name):
    """
    doctype: Name of doctype (e.g. 'Customer')
    identifiers: dict mapping keys to fields {'name': 'name1', 'email': 'email', 'mobile': 'mobile'}
    role_name: Role to assign
    """
    docs = frappe.get_all(doctype, fields=["name", identifiers['name'], identifiers.get('email', 'name'), identifiers.get('mobile', 'name'), "linked_user"])
    
    for d in docs:
        if d.linked_user and frappe.db.exists("User", d.linked_user):
            print(f"Skipping {d.name}, already linked to {d.linked_user}")
            # Ensure role is assigned even if linked
            user = frappe.get_doc("User", d.linked_user)
            user.add_roles(role_name)
            continue
            
        # Determine email
        email = d.get(identifiers.get('email'))
        if not email or "@" not in email:
            # Generate fake email if missing
            sanitized_name = d.get(identifiers['name']).replace(" ", "").lower()
            email = f"{sanitized_name}_{random_string(5)}@example.com"
        
        first_name = d.get(identifiers['name'])
        
        if not frappe.db.exists("User", email):
            user = frappe.new_doc("User")
            user.email = email
            user.first_name = first_name
            user.send_welcome_email = 0
            user.enabled = 1
            user.insert(ignore_permissions=True)
            print(f"Created User: {email} for {doctype} {d.name}")
        else:
            user = frappe.get_doc("User", email)
            
        user.add_roles(role_name)
        
        # Link back
        frappe.db.set_value(doctype, d.name, "linked_user", user.name)
        print(f"Linked {doctype} {d.name} -> User {user.name}")


def execute():
    # 1. Create Roles
    create_role_if_not_exists("Customer")
    create_role_if_not_exists("Driver")
    create_role_if_not_exists("Vendor")
    
    frappe.db.commit()

    # 2. Customers
    # schema: name1, email, mobile
    create_user_and_link("Customer", {'name': 'name1', 'email': 'email', 'mobile': 'mobile'}, "Customer")
    
    # 3. Drivers
    # schema: name1, mobile (no email usually, check schema)
    # Drivers schema has 'name1', 'mobile'. No email field in standard mock, so we generate one.
    create_user_and_link("Drivers", {'name': 'name1', 'mobile': 'mobile'}, "Driver")
    
    # 4. Vendors
    # schema: company_name, email, mobile, owner_name
    create_user_and_link("Vendors", {'name': 'company_name', 'email': 'email'}, "Vendor")

    frappe.db.commit()
    print("User setup complete.")
