import frappe

def run():
    print("Checking for 'Welcome Workspace'...")
    
    if not frappe.db.exists("Workspace", "Welcome Workspace"):
        print("'Welcome Workspace' not found. Creating it...")
        try:
            doc = frappe.get_doc({
                "doctype": "Workspace",
                "label": "Welcome Workspace",
                "name": "Welcome Workspace",
                "title": "Welcome Workspace",
                "public": 1,
                "content": "[]"
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            print("Created 'Welcome Workspace'.")
        except Exception as e:
            print(f"Failed to create workspace: {e}")
            frappe.db.rollback()
    else:
        print("'Welcome Workspace' already exists.")
        
    # List all workspaces to see what exists
    print("\nExisting Workspaces:")
    workspaces = frappe.get_all("Workspace", fields=["name", "public", "for_user", "module"])
    for w in workspaces:
        print(f"- {w.name} (Public: {w.public}, User: {w.for_user}, Module: {w.module})")
