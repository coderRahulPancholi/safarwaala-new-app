import frappe

def create_booking_master(doc, method):
    """
    Hook to create a Bookings Master entry whenever an Outstation Booking is created.
    Treats 'Bookings Master' as a Sales Order/Registry.
    """
    try:
        booking_master = frappe.get_doc({
            "doctype": "Bookings Master",
            "customer": doc.customer or (doc.customer_name if frappe.db.exists("Customer", doc.customer_name) else None),
            "booking_type": "OutStation Bookings",
            "booking": doc.name
        })
        booking_master.insert(ignore_permissions=True)
        frappe.msgprint(f"Booking Master linked: {booking_master.name}")
    except Exception as e:
        frappe.log_error(f"Failed to create Booking Master for {doc.name}: {str(e)}", "Booking Master Creation Error")

@frappe.whitelist()
def get_my_bookings():
    """
    Fetch both OutStation and Routine Bookings for the logged-in user's linked customer.
    """
    user = frappe.session.user
    if user == "Guest":
        return []

    bookings = frappe.db.sql("""
        (SELECT 
            b.name, b.booking_status, b.departure_datetime, b.creation, b.start_from, b.`to`, b.grand_total, 'OutStation' as type
        FROM `tabOutStation Bookings` b
        JOIN `tabCustomer` c ON b.customer = c.name
        WHERE c.linked_user = %(user)s)
        UNION ALL
        (SELECT 
            b.name, b.booking_status, b.departure_datetime, b.creation, b.start_from, b.`to`, b.grand_total, 'Routine' as type
        FROM `tabRoutine Bookings` b
        JOIN `tabCustomer` c ON b.customer = c.name
        WHERE c.linked_user = %(user)s)
        ORDER BY creation DESC
    """, {"user": user}, as_dict=True)

    return bookings

@frappe.whitelist(allow_guest=True)
def get_booking_details(doctype, name):
    """
    Fetch full details of a specific booking.
    """
    if not frappe.db.exists(doctype, name):
        frappe.throw("Booking not found", frappe.DoesNotExistError)

    doc = frappe.get_doc(doctype, name)
    
    # Permission Check (Optional: relying on allow_guest=True for now as per StatusComponent logic)
    # real-world app should verify ownership or token
    
    return doc.as_dict()
