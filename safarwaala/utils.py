import frappe

def check_gl_entries():
    entries = frappe.get_all("GL Entry", fields=["name", "voucher_type", "voucher_no", "owner", "debit", "credit"])
    print(f"Total GL Entries: {len(entries)}")
    for entry in entries:
        print(entry)
