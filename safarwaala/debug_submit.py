import frappe
def execute():
    for dt in ["OutStation Bookings", "Vehicle Expense Log"]:
        print(f"--- {dt} ---")
        meta = frappe.get_meta(dt)
        print(f"Is Submittable: {meta.is_submittable}")
        std_perms = frappe.get_doc("DocType", dt).permissions
        for p in std_perms:
            if p.role == "System Manager":
                print(f"Role: {p.role}, Submit: {p.submit}")
