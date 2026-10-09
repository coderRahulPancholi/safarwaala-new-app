frappe.ui.form.on('Lead', {
    refresh: function(frm) {
        if(!frm.is_new() && frm.doc.status !== 'Converted') {
            frm.add_custom_button(__('Create Booking'), function() {
                // Pre-fill a Booking from Lead data
                
                // Open new Booking
                // Lead.booking_type is a label ("Local Booking" / "OutStation Booking");
                // Bookings.booking_type is "Local" / "Outstation".
                const booking_type = (frm.doc.booking_type || '').toLowerCase().startsWith('local') ? 'Local' : 'Outstation';
                frappe.new_doc('Bookings', {
                    'booking_type': booking_type,
                    'customer_name': frm.doc.first_name,
                    'customer_mobile': frm.doc.mobile_no,
                    'pickup_address': frm.doc.pickup_location,
                    'drop_address': frm.doc.drop_location,
                    'pickup_datetime': frm.doc.pickup_datetime,
                    'return_datetime': frm.doc.return_datetime,
                    'car_model': frm.doc.car_model,
                    'trip_type': frm.doc.trip_type,
                    'package_type': frm.doc.package_type
                });
            });
        }
    }
});
