frappe.ui.form.on("Duty Slips", {
	refresh(frm) {
        if(!frm.is_new()) {
            frm.add_custom_button(__("Make Driver Payment"), async function() {
                // Calculate Total Expenses
                let total_expense = 0;
                (frm.doc.expenses || []).forEach(row => {
                    total_expense += (row.amount || 0);
                });

                // Fetch Vendor from Driver
                let vendor = "";
                if(frm.doc.driver) {
                     vendor = await frappe.db.get_value('Drivers', frm.doc.driver, 'owner_vendor');
                     if(vendor && vendor.message) vendor = vendor.message.owner_vendor; 
                     // Handle frappe.db.get_value return format which might be object
                }

                frappe.new_doc("Driver Payment", {
                    booking_type: frm.doc.booking_type,
                    booking_id: frm.doc.booking_id,
                    duty_slip_link: frm.doc.name,
                    driver: frm.doc.driver,
                    vendor: vendor,
                    amount: total_expense,
                    details: "Payment for Duty Slip: " + frm.doc.name
                });
            }, __("Create"));

            frm.add_custom_button(__("Create Expense Log"), function() {
                frappe.new_doc("Vehicle Expense Log", {
                    booking_type: frm.doc.booking_type,
                    booking_ref: frm.doc.booking_id, // Dynamic Link
                    booking_type: frm.doc.booking_type, // Ensure both are passed if needed by link (but booking_type field handles it)
                    driver: frm.doc.driver,
                    car: frm.doc.car,
                    expense_date: frappe.datetime.get_today()
                });
            }, __("Create"));
        }
	},
});
