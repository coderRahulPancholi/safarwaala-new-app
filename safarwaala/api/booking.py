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
    vendor = frappe.db.get_value("Vendors", {"linked_user": user}, "name")

    filters = []
    if driver:
        filters.append(f"driver = '{driver}'")
    if customer:
        filters.append(f"customer = '{customer}'")
    if vendor:
        filters.append(f"assigned_to = '{vendor}'")
    
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
def manage_duty_slip(booking_id, action="create", **kwargs):
    """
    Create or Update a Duty Slip for a booking.
    """
    try:
        # Check if Duty Slip exists for this booking
        ds_name = frappe.db.exists("Duty Slips", {"booking_id": booking_id})
        
        if ds_name:
            doc = frappe.get_doc("Duty Slips", ds_name)
            if doc.docstatus == 1:
                return {"success": False, "message": "Duty Slip is already submitted and cannot be edited."}
        else:
            if action != "create":
                 return {"success": False, "message": "Duty Slip not found"}
            
            # Create new
            booking_doc = frappe.get_doc("OutStation Bookings", booking_id) # Or Routine
            doc = frappe.new_doc("Duty Slips")
            doc.booking_type = "OutStation Bookings" # Should make dynamic if supporting Routine
            doc.booking_id = booking_id
            doc.driver = booking_doc.driver
            doc.car = booking_doc.car
            doc.car_modal = booking_doc.car_modal
            doc.customer = booking_doc.customer
        
        # Update fields
        if "start_km" in kwargs: doc.start_km = kwargs.get("start_km")
        if "end_km" in kwargs: doc.end_km = kwargs.get("end_km")
        if "departure_datetime" in kwargs: doc.departure_datetime = kwargs.get("departure_datetime")
        if "return_datetime" in kwargs: doc.return_datetime = kwargs.get("return_datetime")
        
        doc.save(ignore_permissions=True)
        
        if action == "submit":
            doc.submit()
            
        return {"success": True, "message": "Duty Slip updated", "data": doc.name}

    except Exception as e:
        frappe.log_error(f"Duty Slip Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_booking_expenses(booking_id):
    """
    Fetch all Vehicle Expense Logs linked to this booking.
    """
    return frappe.db.get_all("Vehicle Expense Log", 
        filters={"booking_ref": booking_id}, 
        fields=["name", "expense_type", "amount", "expense_date", "status", "receipt_image"]
    )

@frappe.whitelist()
def get_duty_slip_details(booking_id):
    ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
    if ds_name:
        return frappe.get_doc("Duty Slips", ds_name).as_dict()
    return None

@frappe.whitelist()
def log_expense(expense_type, amount, car=None, paid_by="Driver", driver=None, booking_ref=None, booking_type=None, expense_date=None, receipt_image=None, is_billable=0):
    """
    Log a vehicle expense. Auto-fetches car/driver from booking if not provided.
    """
    try:
        # Auto-set billable for Toll/Parking
        if not is_billable and expense_type in ["Toll", "Parking"]:
            is_billable = 1
        
        # Dynamic Fetch from Booking
        if booking_ref:
            # Try to infer booking_type if missing, or fetch car/driver if missing
            b_doc = None
            inferred_type = None

            if frappe.db.exists("OutStation Bookings", booking_ref):
                b_doc = frappe.get_doc("OutStation Bookings", booking_ref)
                inferred_type = "OutStation Bookings"
            elif frappe.db.exists("Routine Bookings", booking_ref):
                b_doc = frappe.get_doc("Routine Bookings", booking_ref)
                inferred_type = "Routine Bookings"
            
            # Set booking_type if not provided
            if not booking_type and inferred_type:
                booking_type = inferred_type

            # Set car/driver if missing and we found the doc
            if b_doc:
                if not car: car = b_doc.car
                if not driver: driver = b_doc.driver

        if not car:
            return {"success": False, "message": "Car is required and could not be fetched from booking."}

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
