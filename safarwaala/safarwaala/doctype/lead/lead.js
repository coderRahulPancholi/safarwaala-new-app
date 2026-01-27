frappe.ui.form.on('Lead', {
    refresh: function(frm) {
        if(!frm.is_new() && frm.doc.status !== 'Converted') {
            frm.add_custom_button(__('Create Booking'), function() {
                // Pre-fill Booking Master from Lead data
                
                // Open new Booking Master
                frappe.new_doc('Bookings Master', {
                    'customer_name': frm.doc.first_name,
                    'customer_mobile': frm.doc.mobile_no,
                    'customer_email': frm.doc.email_id,
                    'pickup_location': frm.doc.pickup_location,
                    'drop_location': frm.doc.drop_location,
                    'from_city': frm.doc.from_city,
                    'to_city': frm.doc.to_city,
                    'pickup_datetime': frm.doc.pickup_datetime,
                    'return_datetime': frm.doc.return_datetime,
                    'car_modal': frm.doc.car_modal,
                    'trip_type': frm.doc.trip_type,
                    'min_km': frm.doc.min_km,
                    'min_hours': frm.doc.min_hours,
                    'package_type': frm.doc.package_type
                    // booking_type field in Booking Master needs careful handling if it drives logic
                });
            });
        }
    }
});
