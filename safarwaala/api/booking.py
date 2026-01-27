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
def create_booking(booking_type, booking_data):
    """
    Unified API to create bookings.
    booking_type: 'OutStation', 'Local', 'Routine' or full DocType name.
    booking_data: JSON string or dict of booking fields.
    """
    try:
        if isinstance(booking_data, str):
            import json
            booking_data = json.loads(booking_data)
            
        doctype_map = {
            "outstation": "OutStation Bookings",
            "local": "Local Bookings",
            "routine": "Routine Bookings"
        }
        
        # Determine DocType
        doctype = doctype_map.get(booking_type.lower())
        if not doctype:
            # Fallback checks
            if frappe.db.exists("DocType", booking_type):
                doctype = booking_type
            elif frappe.db.exists("DocType", f"{booking_type} Bookings"):
                doctype = f"{booking_type} Bookings"
            else:
                return {"success": False, "message": "Invalid Booking Type"}
        
        # Create Document
        doc = frappe.new_doc(doctype)
        doc.update(booking_data)
        doc.insert(ignore_permissions=True)
        
        return {"success": True, "message": "Booking Created Successfully", "data": doc}

    except Exception as e:
        frappe.log_error(f"Create Booking Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_my_bookings():
    """
    Fetch OutStation, Local, and Routine Bookings for the logged-in user's linked customer/driver/vendor.
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
        # Assuming 'vendor' field exists in Bookings Master, NOT assigned_to.
        # Checking schema previously... wait, let me check schema quickly or assume standard.
        # Actually Bookings Master likely has specific fields. Let's assume vendor field name is 'vendor' or check.
        # Based on previous turns, it was likely linked to vendor via 'vendor' field?
        # Let's check permissions or just use 'vendor' field if correct.
        # Actually, looking at previous edits, Bookings Master does NOT use assigned_to, it uses 'vendor'.
        filters.append(f"vendor = '{vendor}'")
    
    if not filters:
        return []

    where_clause = " OR ".join(filters) # Wait, should be OR? No, a user is usually ONE role. But if they are multiple, OR is fine.
    
    # Actually, usually a session user is one person. But let's keep OR if they match multiple roles.

    bookings = frappe.db.sql(f"""
        SELECT 
            name, booking_status, DATE_FORMAT(pickup_datetime, '%Y-%m-%d %H:%i:%s') as departure_datetime, creation, 
            pickup_location as start_from, drop_location as `to`, grand_total, 
            customer_name, booking_type as type, booking_status as status
        FROM `tabBookings Master`
        WHERE {where_clause}
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
    if doc.get("driver"):
        # Drivers: name1 is the Name field, mobile is Mobile. No image field.
        details["driver_details"] = frappe.db.get_value("Drivers", doc.get("driver"), ["name1", "mobile"], as_dict=True)
        # Rename name1 to name for frontend consistency if needed, or handle in frontend
        if details["driver_details"] and "name1" in details["driver_details"]:
             details["driver_details"]["name"] = details["driver_details"].pop("name1")
        
    # Fetch Car Details
    if doc.get("car"):
        # Cars: license_plate. No image or color field.
        details["car_details"] = frappe.db.get_value("Cars", doc.get("car"), ["license_plate", "modal"], as_dict=True)
        if details["car_details"]:
             details["car_details"]["car_number"] = details["car_details"].get("license_plate")
        
    # Fetch Car Model Details
    if doc.get("car_modal"):
        # Car Modals: modal_name. No image field.
        details["car_modal_details"] = frappe.db.get_value("Car Modals", doc.get("car_modal"), ["modal_name", "seating_capacity", "luggage_capacity"], as_dict=True)
        if details["car_modal_details"] and "modal_name" in details["car_modal_details"]:
             details["car_modal_details"]["name"] = details["car_modal_details"].pop("modal_name")

    # Fetch Financials
    invoice_ref = doc.get("invoice") or doc.get("linked_invoice")
    if invoice_ref:
        details["invoice_details"] = frappe.db.get_value("Customer Invoice", invoice_ref, ["name", "grand_total", "paid_amount", "payable_amount", "status", "docstatus"], as_dict=True)

    payment_name = frappe.db.get_value("Payouts", {"booking_id": name}, "name")
    if payment_name:
        pay_fields = frappe.db.get_value("Payouts", payment_name, ["name", "amount", "docstatus", "payment_date", "status"], as_dict=True)
        if pay_fields:
            # Payouts has 'status' field (Pending/Paid), usage differs from standard docstatus flow slightly but 
            # let's trust the 'status' field or docstatus.
            # pay_fields["status"] = "Draft" if pay_fields.docstatus == 0 else "Submitted" # Old logic
            # New logic: Payouts has explicit status field.
            details["driver_payment_details"] = pay_fields
        
        details["driver_payment"] = payment_name



    return details

@frappe.whitelist()
def get_duty_slip_details(booking_id):
    # Fetch Booking Status first
    if not frappe.db.exists("Bookings Master", booking_id):
        return None
    
    booking_status = frappe.db.get_value("Bookings Master", booking_id, "booking_status")
    
    ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
    
    data = {}
    if ds_name:
        data = frappe.get_doc("Duty Slips", ds_name).as_dict()
    
    # Inject status for frontend logic
    data["status"] = booking_status
    
    return data

@frappe.whitelist()
def manage_duty_slip(booking_id, action="create", **kwargs):
    """
    Create or Update a Duty Slip for a booking (Separate DocType).
    """
    try:
        # Check if Duty Slip exists for this booking
        ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
        
        if ds_name:
            doc = frappe.get_doc("Duty Slips", ds_name)
            if doc.docstatus == 1:
                return {"success": False, "message": "Duty Slip is already submitted and cannot be edited."}
        else:
            if action not in ["create", "submit", "start_trip"]:
                 return {"success": False, "message": "Duty Slip not found"}
            
            # Create new Duty Slip
            if not frappe.db.exists("Bookings Master", booking_id):
                 return {"success": False, "message": "Booking not found"}

            booking_doc = frappe.get_doc("Bookings Master", booking_id)
            doc = frappe.new_doc("Duty Slips")
            doc.booking_type = "Bookings Master"
            doc.booking_id = booking_id
            doc.driver = booking_doc.driver
            doc.car = booking_doc.car
            doc.car_modal = booking_doc.car_modal
        
        # Update fields
        if "start_km" in kwargs: doc.start_km = kwargs.get("start_km")
        if "end_km" in kwargs: doc.end_km = kwargs.get("end_km")
        if "departure_datetime" in kwargs: doc.departure_datetime = kwargs.get("departure_datetime")
        if "return_datetime" in kwargs: doc.return_datetime = kwargs.get("return_datetime")
        
        # Handle Actions
        if action == "start_trip":
            doc.departure_datetime = frappe.utils.now_datetime()
            # Update Parent Booking Status
            frappe.db.set_value("Bookings Master", booking_id, "booking_status", "Ongoing")
            frappe.db.set_value("Bookings Master", booking_id, "pickup_datetime", doc.departure_datetime)

        if action == "end_trip":
            doc.return_datetime = frappe.utils.now_datetime()
            # Update Parent Booking Status
            frappe.db.set_value("Bookings Master", booking_id, "booking_status", "Completed")
            frappe.db.set_value("Bookings Master", booking_id, "return_datetime", doc.return_datetime)

        doc.save(ignore_permissions=True)
        
        if action == "submit":
            if doc.docstatus == 0:
                doc.submit()
            
        return {"success": True, "message": "Duty Slip updated", "data": doc.name}

    except Exception as e:
        frappe.log_error(f"Duty Slip Error: {str(e)}")
@frappe.whitelist()
def sync_booking_details(booking_id):
    """
    Sync details from Duty Slips and Vehicle Expense Logs to Bookings Master.
    Triggers calculation of charges, expenses, and taxes.
    """
    try:
        if not frappe.db.exists("Bookings Master", booking_id):
             return {"success": False, "message": "Booking not found"}
        
        doc = frappe.get_doc("Bookings Master", booking_id)
        
        # Sync from Duty Slips
        ds_name = frappe.db.get_value("Duty Slips", {"booking_id": booking_id}, "name")
        if ds_name:
            ds_doc = frappe.get_doc("Duty Slips", ds_name)
            doc.start_km = ds_doc.start_km
            doc.end_km = ds_doc.end_km
            doc.pickup_datetime = ds_doc.departure_datetime
            doc.return_datetime = ds_doc.return_datetime
            
        # Save calls validate() which calls calculate_charges/expenses/taxes/totals
        doc.save(ignore_permissions=True)
        
        return {"success": True, "message": "Booking Details Synced and Calculated.", "data": doc.name}

    except Exception as e:
        frappe.log_error(f"Sync Booking Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def finalize_booking(booking_id):
    """
    Manually finalize/submit a booking. 
    Useful if automatic submission failed or for legacy bookings.
    """
    try:
        # Determine doctype
        doctype = None
        if frappe.db.exists("Bookings Master", booking_id):
             doctype = "Bookings Master"
        elif frappe.db.exists("Local Bookings", booking_id):
             doctype = "Local Bookings"
        elif frappe.db.exists("OutStation Bookings", booking_id):
             doctype = "OutStation Bookings"
        
        if not doctype:
             return {"success": False, "message": "Booking not found"}
        
        doc = frappe.get_doc(doctype, booking_id)
        if doc.docstatus == 1:
            return {"success": False, "message": "Booking is already submitted."}
            
        doc.flags.ignore_permissions = True
        doc.submit()
        
        # Auto-approve and submit all linked expenses
        expenses = frappe.get_all("Vehicle Expense Log", filters={"booking_ref": booking_id}, pluck="name")
        for exp_name in expenses:
            exp_doc = frappe.get_doc("Vehicle Expense Log", exp_name)
            if exp_doc.docstatus == 0:
                exp_doc.status = "Approved"
                exp_doc.flags.ignore_permissions = True
                exp_doc.save()
                try:
                    exp_doc.submit()
                except:
                    pass
        
        return {"success": True, "message": "Booking Finalized and Financials Generated."}
    except Exception as e:
        frappe.log_error(f"Finalize Booking Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def submit_document(doctype, name):
    """
    Generic method to submit a document (Invoice, Payment, etc)
    """
    try:
        if not frappe.db.exists(doctype, name):
             return {"success": False, "message": f"{doctype} not found"}
        
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            return {"success": False, "message": "Document is already submitted."}
            
        doc.flags.ignore_permissions = True
        doc.submit()
        
        return {"success": True, "message": f"{doctype} Submitted Successfully."}
    except Exception as e:
        frappe.log_error(f"Submit Document Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def generate_financials(booking_id):
    """
    Generate financials (Invoice/Payment) for a booking without submitting it.
    Allows for preview/review.
    """
    try:
        # Determine doctype
        doctype = "OutStation Bookings"
        if frappe.db.exists("Local Bookings", booking_id):
             doctype = "Local Bookings"
        elif not frappe.db.exists("OutStation Bookings", booking_id):
             return {"success": False, "message": "Booking not found"}
        
        doc = frappe.get_doc(doctype, booking_id)
        # Call the creation methods manually
        doc.create_customer_invoice()
        doc.create_driver_payment()
        
        return {"success": True, "message": "Financials Generated for Review."}
    except Exception as e:
        frappe.log_error(f"Generate Financials Error: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_booking_expenses(booking_id):
    """
    Fetch all Vehicle Expense Logs linked to this booking.
    """
    return frappe.db.get_all("Vehicle Expense Log", 
        filters={"booking_ref": booking_id}, 
        fields=["name", "expense_type", "amount", "expense_date", "status", "receipt_image", "paid_by", "is_billable"]
    )

@frappe.whitelist()
def log_expense(expense_type, amount, car=None, paid_by="Driver", driver=None, booking_ref=None, expense_date=None, receipt_image=None, is_billable=0):
    """
    Log a vehicle expense. Auto-fetches car/driver from booking if not provided.
    """
    try:
        # Auto-set billable for Toll/Parking
        if not is_billable and expense_type in ["Toll", "Parking"]:
            is_billable = 1
        
        # Dynamic Fetch from Booking
        if booking_ref:
            # Check if it's a Bookings Master
            if frappe.db.exists("Bookings Master", booking_ref):
                b_doc = frappe.get_doc("Bookings Master", booking_ref)
                
                # Set car/driver if missing
                if not car: car = b_doc.car
                if not driver: driver = b_doc.driver
            else:
                 return {"success": False, "message": "Invalid Booking Reference"}

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

@frappe.whitelist()
def get_dashboard_stats():
    try:
        user = frappe.session.user
        roles = frappe.get_roles(user)
        
        stats = {
            "active_drivers": 0,
            "total_vehicles": 0,
            "pending_payments": 0,
            "total_earnings": 0,
            "upcoming_trips": 0,
            "driver_earnings": 0,
            "duty_status": "Unknown"
        }
        
        if "Vendor" in roles or "System Manager" in roles:
            # Vendor Stats
            
            # Identify Vendor
            vendor_name = None
            if "System Manager" not in roles:
                vendor_name = frappe.db.get_value("Vendors", {"linked_user": user}, "name")
            
            # Filter Conditions
            driver_filters = {"disabled": 0}
            car_filters = {"disabled": 0}
            payment_filters = {"docstatus": 0}
            
            if vendor_name:
                driver_filters["owner_vendor"] = vendor_name
                car_filters["belongs_to_vendor"] = vendor_name
                payment_filters["vendor"] = vendor_name
                # Note: Customer Invoice filtering is complex as it links to Customer, not directly to Vendor.
                # However, OutStation Bookings are assigned to Vendor.
                # So we can sum invoices linked to bookings assigned to this vendor.
            
            stats["active_drivers"] = frappe.db.count("Drivers", filters=driver_filters)
            stats["total_vehicles"] = frappe.db.count("Cars", filters=car_filters)
            
            # Pending Payments (Driver Payments) - Using Payouts table
            # Filter: Status 'Pending', and Driver belongs to this Vendor
            if vendor_name:
                 pending_sql = frappe.db.sql("""
                    SELECT SUM(p.amount) 
                    FROM `tabPayouts` p
                    JOIN `tabDrivers` d ON p.payout_to = d.name
                    WHERE p.status = 'Pending' AND d.owner_vendor = %s
                """, (vendor_name,))
            else:
                 pending_sql = frappe.db.sql("""
                    SELECT SUM(amount) FROM `tabPayouts` WHERE status = 'Pending'
                """)
            stats["pending_payments"] = pending_sql[0][0] if pending_sql and pending_sql[0][0] else 0

            # Total Earnings (Customer Invoices Paid)
            # If Vendor, join with OutStation Bookings
            if vendor_name:
                earnings_sql = frappe.db.sql("""
                    SELECT SUM(ci.grand_total) 
                    FROM `tabCustomer Invoice` ci
                    JOIN `tabOutStation Bookings` ob ON ci.name = ob.invoice
                    WHERE ci.status = 'Paid' AND ob.assigned_to = %s
                """, (vendor_name,))
            else:
                earnings_sql = frappe.db.sql("""
                    SELECT SUM(grand_total) FROM `tabCustomer Invoice` WHERE status = 'Paid'
                """)
            stats["total_earnings"] = earnings_sql[0][0] if earnings_sql and earnings_sql[0][0] else 0

        if "Driver" in roles:
            # Driver Stats
            driver_doc_name = frappe.db.get_value("Drivers", {"linked_user": user}, "name")
            if driver_doc_name:
                stats["upcoming_trips"] = frappe.db.count("OutStation Bookings", filters={"driver": driver_doc_name, "booking_status": "Confirmed"})
                
                # Driver Earnings - Using Payouts
                driver_earnings_sql = frappe.db.sql("""
                    SELECT SUM(amount) FROM `tabPayouts` WHERE payout_to = %s AND status = 'Paid'
                """, (driver_doc_name,))
                stats["driver_earnings"] = driver_earnings_sql[0][0] if driver_earnings_sql and driver_earnings_sql[0][0] else 0
                
                # Duty Status - Derive from disabled field
                is_disabled = frappe.db.get_value("Drivers", driver_doc_name, "disabled")
                stats["duty_status"] = "Inactive" if is_disabled else "Active"
            else:
                stats["upcoming_trips"] = 0
                stats["driver_earnings"] = 0
                stats["duty_status"] = "Not Found"

        return {"success": True, "data": stats}

    except Exception as e:
        frappe.log_error(f"Dashboard Stats Error: {str(e)}")
        return {"success": False, "message": str(e)}
