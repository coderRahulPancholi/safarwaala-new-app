// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Invoice", {
  onload(frm) {
	frm.fields_dict['invoice_item'].grid.get_field('booking_id').get_query = function (doc, cdt, cdn) {
      return {
        filters: {
          booking_status: ['!=', 'Invoiced'],
		  docstatus: ['=', 0],
        }
      };
    };
	frm.fields_dict['invoice_item'].grid.get_field('booking_type').get_query = function (doc, cdt, cdn) {
      return {
        filters: {
          module: ['=', 'Booking Types']
        }
      };
    };
  },
  before_save(frm) {
	
    // Check if the customer invoice item table is empty
    if (
      frm.doc.invoice_item &&
      frm.doc.invoice_item.length > 0
    ) {
      let gross_total = 0;

      // Loop through each item in the child table
      frm.doc.invoice_item.forEach((item) => {
        gross_total += item.amount || 0;
      });

	  
      // Set the values in the parent form
	  grandTotal= gross_total - (frm.doc.discount || 0);

      frm.set_value("gross_total", gross_total);
      frm.set_value("grand_total", grandTotal);
      frm.set_value("payable_amount", grandTotal - (frm.doc.paid_amount || 0));
    } else {
      // If the child table is empty, set the values to 0
      frm.set_value("grand_total", 0);
      frm.set_value("gross_total", 0);

    }
  },
});

frappe.ui.form.on("Customer Invoice Item", {
  booking_id: function (frm, cdt, cdn) {
    auto_fill_values(frm, cdt, cdn);
  },
  booking_type: function (frm, cdt, cdn) {
    auto_fill_values(frm, cdt, cdn);
  },
});

const auto_fill_values = function (frm, cdt, cdn) {
  let row = locals[cdt][cdn];
  if (!row.booking_id || !row.booking_type) return;

  frappe.db
    .get_doc(row.booking_type, row.booking_id)
    .then((doc) => {
      // Example: fetch data from the booking
    //   row.net_amount = doc.net_total || 0;
    //   row.tax_and_services = doc.tax_total || 0;
    //   row.total = doc.total||0;
    //   row.discount = doc.discount || 0;
      row.amount = doc.grand_total;
      frm.refresh_field("customer_invoice_item"); // Replace with your child table fieldname if different
    })
    .catch((err) => {
      console.error("Failed to fetch booking", err);
      frappe.msgprint("Could not fetch booking data.");
    });
};
