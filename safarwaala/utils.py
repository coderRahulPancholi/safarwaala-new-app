import frappe

def check_gl_entries():
    entries = frappe.get_all("GL Entry", fields=["name", "voucher_type", "voucher_no", "owner", "debit", "credit"])
    print(f"Total GL Entries: {len(entries)}")
    for entry in entries:
        print(entry)


def handle_success(message: str, data=None):
    return {
        "status": "success",
        "message": message,
        "data": data,
    }

def handle_error(message: str, data=None):
    frappe.log_error(message=str(data), title=message)
    frappe.throw(message)
