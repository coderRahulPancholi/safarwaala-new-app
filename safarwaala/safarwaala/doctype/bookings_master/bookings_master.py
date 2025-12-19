# Copyright (c) 2025, rahul and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, time_diff_in_hours, ceil, nowdate

class BookingsMaster(Document):
    def validate(self):
        self.calculate_charges()
        self.calculate_expenses()
        self.calculate_taxes()
        self.calculate_totals()

    def before_save(self):
        self.validate()

    def before_insert(self):
        if not self.assigned_to:
            # If user is a Vendor, auto-assign
            if "Vendor" in frappe.get_roles(frappe.session.user):
                 vendor = frappe.db.get_value("Vendors", {"linked_user": frappe.session.user}, "name")
                 if vendor:
                     self.assigned_to = vendor

    def calculate_charges(self):
        # Fetch rates from Car Modal if missing
        if self.car_modal:
            car = frappe.get_doc("Car Modals", self.car_modal)
            if self.booking_type == "Local":
                if not self.min_hours: self.min_hours = car.min_local_hour
                if not self.min_km: self.min_km = car.min_local_km
                if not self.per_hour_rate: self.per_hour_rate = car.local_hour_rate
                if not self.per_km_rate: self.per_km_rate = car.local_km_rate
                if not self.night_rate: self.night_rate = car.night_rate
            elif self.booking_type == "Outstation":
                if not self.per_km_rate: self.per_km_rate = car.per_km_rate
                if not self.night_rate: self.night_rate = car.night_rate
                # We need min_km_day for calculation if min_km is not set
                # Store it in a temporary attribute if needed or use directly
                self._min_km_day = car.min_km_day

        if self.booking_type == "Local":
            self.calculate_local_charges()
        elif self.booking_type == "Outstation":
            self.calculate_outstation_charges()
        
    def calculate_local_charges(self):
        # Base Charges
        base_h = flt(self.min_hours)
        rate_h = flt(self.per_hour_rate)
        self.base_amount = base_h * rate_h

        # Running Details
        if self.start_km is not None and self.end_km is not None:
            self.total_km = flt(self.end_km) - flt(self.start_km)
            if self.total_km < 0: self.total_km = 0
        else:
            self.total_km = 0

        if self.pickup_datetime and self.return_datetime:
            pickup = get_datetime(self.pickup_datetime)
            drop = get_datetime(self.return_datetime)
            # Calculate hours diff
            diff_hours = time_diff_in_hours(drop, pickup)
            if diff_hours < 0: diff_hours = 0
        else:
            diff_hours = 0

        # Extra Charges
        # Extra Hours
        extra_h = flt(diff_hours) - base_h
        if extra_h < 0: extra_h = 0
        self.extra_hour_charges = extra_h * rate_h

        # Extra Km
        base_km = flt(self.min_km)
        extra_k = flt(self.total_km) - base_km
        if extra_k < 0: extra_k = 0
        rate_k = flt(self.per_km_rate)
        self.extra_km_charges = extra_k * rate_k

        # Night Charges: Handled via manual input or auto-calc if needed
        # Assuming manual input 'nights' isn't on master yet, relying on 'night_charges' field directly
        # If 'nights' field existed we would do: self.night_charges = self.nights * self.night_rate
        # For now, let's trust formatting/client script to set night_charges or calc if mapped
        pass

    def calculate_outstation_charges(self):
        if not self.pickup_datetime or not self.return_datetime:
            return

        start = get_datetime(self.pickup_datetime)
        end = get_datetime(self.return_datetime)
        
        # Calculate Days & Nights
        duration_in_seconds = (end - start).total_seconds()
        days = ceil(duration_in_seconds / (24 * 3600))
        if days < 1: days = 1
        
        # Min KM Calculation
        # Use existing min_km if set (assumed Total), else calc from rate
        if not self.min_km:
             min_km_day = getattr(self, '_min_km_day', 0)
             if not min_km_day and self.car_modal:
                 min_km_day = frappe.db.get_value("Car Modals", self.car_modal, "min_km_day")
             self.min_km = flt(min_km_day) * days

        # Running Details
        start_km = flt(self.start_km)
        end_km = flt(self.end_km)
        diff_km = end_km - start_km
        if diff_km < 0: diff_km = 0
        self.total_km = diff_km

        # Chargeable KM
        chargeable_km = max(diff_km, flt(self.min_km))
        
        # Amounts
        per_km_rate = flt(self.per_km_rate)
        self.base_amount = chargeable_km * per_km_rate # Using base_amount for the main KM charge
        
        # Night Charges
        nights = days - 1
        if nights < 0: nights = 0
        self.night_charges = nights * flt(self.night_rate)

        # Clear Local fields
        self.extra_km_charges = 0
        self.extra_hour_charges = 0

    def calculate_expenses(self):
        # Fetch linked Vehicle Expense Logs
        # We find logs linked to this booking reference.
        # We remove strict booking_type dependency for flexibility, 
        # but in practice it should be 'Bookings Master'.
        
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={
                                          'booking_ref': self.name
                                      }, 
                                      fields=['amount', 'is_billable', 'paid_by'])
        
        self.expense_total = sum([flt(d.amount) for d in expenses])
        self.billable_expense_total = sum([flt(d.amount) for d in expenses if d.is_billable])
        self.driver_expense_total = sum([flt(d.amount) for d in expenses if d.paid_by == 'Driver'])

    def calculate_taxes(self):
        self.tax_total = 0
        for row in self.get("tax_and_charges", []):
            self.tax_total += flt(row.amount)

    def calculate_totals(self):
        # Sum up all components
        # Verify component usage based on type
        
        term_total = flt(self.base_amount) + flt(self.night_charges)
        
        if self.booking_type == "Local":
            term_total += flt(self.extra_hour_charges) + flt(self.extra_km_charges)
            
        # Grand Total = Terms + Billable Expenses + Taxes
        # (Assuming Driver paid non-billable expenses are NOT charged to customer, 
        # but Billable ones ARE, regardless of who paid (if driver paid billable, we reimburse driver AND charge customer))
        
        self.grand_total = term_total + flt(self.billable_expense_total) + flt(self.tax_total)

    def on_submit(self):
        self.submit_expenses()
        self.create_customer_invoice()
        self.create_driver_payment()

    def submit_expenses(self):
        # Navigate to linked expenses and submit them
        expenses = frappe.db.get_list('Vehicle Expense Log', 
                                      filters={'booking_ref': self.name, 'docstatus': 0})
        for expense in expenses:
            frappe.get_doc("Vehicle Expense Log", expense.name).submit()

    def create_customer_invoice(self):
        if frappe.db.exists("Customer Invoice", {"booking_id": self.name}):
            return

        # Calculate what customer has already paid via expenses (if any)
        # e.g. Customer paid for fuel directly
        customer_paid_expenses = frappe.db.sql("""
            SELECT SUM(amount) FROM `tabVehicle Expense Log`
            WHERE booking_ref=%s AND paid_by='Customer' AND docstatus=1
        """, (self.name,))
        
        customer_paid = flt(customer_paid_expenses[0][0]) if customer_paid_expenses else 0.0

        invoice = frappe.get_doc({
            "doctype": "Customer Invoice",
            "customer": self.customer,
            "invoice_date": nowdate(),
            "invoice_due_date": nowdate(),
            "invoice_item": [{
                # "booking_type" removed from schema
                "booking_id": self.name,
                "amount": self.grand_total,
                "description": f"{self.booking_type} Booking Charges"
            }],
            "gross_total": self.grand_total,
            "grand_total": self.grand_total,
            "paid_amount": customer_paid,
            "payable_amount": self.grand_total - customer_paid,
             # If we want to verify user/vendor, we might add 'vendor': self.assigned_to here if the schema expects it
             "vendor": self.assigned_to 
        })
        invoice.insert(ignore_permissions=True)
        
        # Update Booking with Invoice details
        self.db_set("booking_status", "Invoiced")
        self.db_set("linked_invoice", invoice.name)
        
        frappe.msgprint(_("Customer Invoice {0} created").format(invoice.name))

    def create_driver_payment(self):
        if frappe.db.exists("Driver Payment", {"booking_id": self.name}):
            return

        # Driver Payment = Night Charges (Allowance) + Driver Paid Expenses
        # (Assuming Base/Extra charges belong to the vendor/company)
        
        allowance = flt(self.night_charges) 
        
        # We already calc driver_expense_total (all expenses paid by driver)
        # Re-verify if we only reimburse 'valid' expenses? For now assume all logged driver expenses are reimbursable.
        reimbursement = flt(self.driver_expense_total)
        
        total_pay = allowance + reimbursement
        
        if total_pay <= 0: return

        if not self.driver: return 
        
        driver_doc = frappe.get_doc("Drivers", self.driver)
        vendor = driver_doc.owner_vendor
        
        payment = frappe.get_doc({
            "doctype": "Driver Payment",
            "booking_type": self.doctype,
            "booking_id": self.name,
            "driver": self.driver,
            "vendor": vendor,
            "amount": total_pay,
            "status": "Pending",
            "payment_date": nowdate(),
            "details": f"Allowance: {allowance}, Reimbursement: {reimbursement}"
        })
        payment.insert(ignore_permissions=True)
        frappe.msgprint(_("Driver Payment {0} created").format(payment.name))
