// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Invoice", {
	refresh(frm) {

	},
});
frappe.ui.form.on("Customer Invoice Item", {
	booking_id: function(frm, cdt, cdn) {
        auto_fill_values(frm, cdt, cdn);	
	},
    booking_type: function(frm, cdt, cdn) {
        auto_fill_values(frm, cdt, cdn);	
    },
});

const auto_fill_values = function(frm, cdt, cdn) {
    console.log("auto_fill_values",cdn,cdt);
    
    let row = locals[cdt][cdn];
		if (!row.booking_id || !row.booking_type) return;

		frappe.db.get_doc(row.booking_type, row.booking_id)
			.then(doc => {
				// Example: fetch data from the booking
				row.net_amount = doc.net_amount || 1;
				row.tax_and_services = doc.tax_total || 0;
				row.total = doc.net_amount + doc.tax_total;
				row.payable_amount = doc.net_amount + doc.tax_total;
				frm.refresh_field("customer_invoice_item"); // Replace with your child table fieldname if different
			})
			.catch(err => {
				console.error("Failed to fetch booking", err);
				frappe.msgprint("Could not fetch booking data.");
			});
}