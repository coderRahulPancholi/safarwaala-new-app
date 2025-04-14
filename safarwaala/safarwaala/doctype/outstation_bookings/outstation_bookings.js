// Copyright (c) 2025, rahul and contributors
// For license information, please see license.txt

frappe.ui.form.on("OutStation Bookings", {
	refresh(frm) {

	},
    start_km(frm){
        calculateDiffrence(frm);

    },
    end_km(frm){
        calculateDiffrence(frm);
    },
    per_km_rate(frm){
        calculateKmAmount(frm);
    },
    diffrence_km(frm){
        calculateKmAmount(frm);
    },
});



const calculateDiffrence = (frm) => {
    const start_km = frm.doc.start_km;
    const end_km = frm.doc.end_km;
    const diffrence = end_km - start_km;
    frm.set_value('diffrence_km', diffrence);
    calculateKmAmount(frm);
}
const calculateKmAmount = (frm) => {
    const diffrence = frm.doc.diffrence_km;
    const rate = frm.doc.per_km_rate;
    const amount = diffrence * rate;
    frm.set_value('km_amount', amount);

}
