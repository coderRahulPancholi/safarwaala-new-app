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

    driver = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
    customer = frappe.db.get_value("Customer", {"linked_user": user}, "name")
    # Vendor logic if needed: vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")

    filters = []
    if driver:
        filters.append(f"driver = '{driver}'")
    if customer:
        filters.append(f"customer = '{customer}'")
    
    # If user is not linked to anything, return relevant bookings (e.g. created by them if they are system user) 
    # or just return empty. For now, if no links, assume empty.
    if not filters:
        # Fallback: check owner?
        # filters.append(f"owner = '{user}'")
        return []

    where_clause = " OR ".join(filters)

    bookings = frappe.db.sql(f"""
        (SELECT 
            name, booking_status, departure_datetime, creation, start_from, `to`, grand_total, customer_name, 'OutStation' as type, booking_status as status
        FROM `tabOutStation Bookings`
        WHERE {where_clause})
        UNION ALL
        (SELECT 
            name, booking_status, departure_datetime, creation, start_from, `to`, grand_total, customer_name, 'Routine' as type, booking_status as status
        FROM `tabRoutine Bookings`
        WHERE {where_clause})
        ORDER BY creation DESC
    """, as_dict=True)

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
    
    details = doc.as_dict()
    
    # Fetch Driver Details
    if doc.driver:
        # Drivers: name1 is the Name field, mobile is Mobile. No image field.
        details["driver_details"] = frappe.db.get_value("Drivers", doc.driver, ["name1", "mobile"], as_dict=True)
        # Rename name1 to name for frontend consistency if needed, or handle in frontend
        if details["driver_details"] and "name1" in details["driver_details"]:
             details["driver_details"]["name"] = details["driver_details"].pop("name1")
        
    # Fetch Car Details
    if doc.car:
        # Cars: license_plate. No image or color field.
        details["car_details"] = frappe.db.get_value("Cars", doc.car, ["license_plate", "modal"], as_dict=True)
        if details["car_details"]:
             details["car_details"]["car_number"] = details["car_details"].get("license_plate")
        
    # Fetch Car Model Details
    if doc.car_modal:
        # Car Modals: modal_name. No image field.
        details["car_modal_details"] = frappe.db.get_value("Car Modals", doc.car_modal, ["modal_name", "seating_capacity", "luggage_capacity"], as_dict=True)
        if details["car_modal_details"] and "modal_name" in details["car_modal_details"]:
             details["car_modal_details"]["name"] = details["car_modal_details"].pop("modal_name")

    return details

@frappe.whitelist()
def log_expense(expense_type, amount, car, paid_by="Driver", driver=None, booking_ref=None, booking_type=None, expense_date=None, receipt_image=None, is_billable=0):
    """
    Log a vehicle expense.
    """
    try:
        # Auto-set billable for Toll/Parking if not explicitly provided
        if not is_billable and expense_type in ["Toll", "Parking"]:
            is_billable = 1

        expense_doc = frappe.get_doc({
            "doctype": "Vehicle Expense Log",
            "expense_date": expense_date or frappe.utils.nowdate(),
            "expense_type": expense_type,
            "amount": amount,
            "is_billable": is_billable,
            "car": car,
            "driver": driver,
            "booking_type": booking_type,
            "booking_ref": booking_ref,
            "paid_by": paid_by,
            "receipt_image": receipt_image,
            "status": "Pending" 
        })
        expense_doc.insert(ignore_permissions=True)
        return {"success": True, "message": "Expense logged successfully", "data": expense_doc.name}
    except Exception as e:
        frappe.log_error(f"Failed to log expense: {str(e)}", "Vehicle Expense Log Error")
        return {"success": False, "message": str(e)}
