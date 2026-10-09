frappe.ui.form.on("Duty Slips", {
	refresh(frm) {
		// Drivers are paid by their vendor, so there is no driver payout here. What we can
		// raise from a completed slip is the Outbound payment to the vendor who ran it.
		if (frm.is_new() || frm.doc.booking_type !== "Bookings" || !frm.doc.booking_id) return;

		frm.add_custom_button(
			__("Pay Vendor"),
			function () {
				frappe.db
					.get_value("Bookings", frm.doc.booking_id, [
						"assigned_to",
						"vendor_outstanding",
					])
					.then((r) => {
						const booking = r.message || {};
						if (!booking.assigned_to) {
							frappe.msgprint(__("This booking has no vendor assigned."));
							return;
						}
						frappe.new_doc("Payments", {
							payment_direction: "Outbound",
							party_type: "Vendors",
							party: booking.assigned_to,
							booking: frm.doc.booking_id,
							amount: booking.vendor_outstanding || 0,
							remarks: __("Settlement for Duty Slip {0}", [frm.doc.name]),
						});
					});
			},
			__("Create")
		);
	},
});
