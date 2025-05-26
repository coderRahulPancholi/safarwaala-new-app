// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payments", {
	invoice_type(frm) {
        get_amount(frm);

	},
    invoice_number(frm) {
        get_amount(frm);
    },
});

const get_amount = (frm) => {
if(frm.doc.invoice_type&&frm.doc.invoice_number){
        frappe.db.get_value(frm.doc.invoice_type, frm.doc.invoice_number, "grand_total", (r) => {
            if (r && r.grand_total) {
                frm.set_value("amount", r.grand_total);
            }
        });
    }else{
        frm.set_value("amount", 0);
    }
};
