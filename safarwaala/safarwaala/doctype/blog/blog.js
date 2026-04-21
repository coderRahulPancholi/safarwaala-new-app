// Copyright (c) 2026, Safarwaala and contributors
// For license information, please see license.txt

frappe.ui.form.on("Blog", {
    title: function (frm) {
        // Auto-generate slug from title when title changes
        if (!frm.doc.slug || frm.doc.__islocal) {
            frm.set_value("slug", slugify(frm.doc.title || ""));
        }

        // Auto-fill SEO title if empty
        if (!frm.doc.seo_title) {
            frm.set_value("seo_title", (frm.doc.title || "").substring(0, 70));
        }
    },

    short_description: function (frm) {
        // Auto-fill meta description if empty
        if (!frm.doc.meta_description) {
            frm.set_value("meta_description", (frm.doc.short_description || "").substring(0, 160));
        }
    },

    slug: function (frm) {
        // Enforce slug format on user edits
        frm.set_value("slug", slugify(frm.doc.slug || ""));
    },

    refresh: function (frm) {
        // Show live preview URL in the sidebar
        if (frm.doc.slug) {
            frm.set_intro(
                `<b>Frontend URL:</b> /blogs/${frm.doc.slug}`,
                "blue"
            );
        }

        // Character counters for SEO fields
        updateCharCount(frm, "seo_title", 70);
        updateCharCount(frm, "meta_description", 160);
    },

    seo_title: function (frm) {
        updateCharCount(frm, "seo_title", 70);
    },

    meta_description: function (frm) {
        updateCharCount(frm, "meta_description", 160);
    },
});

function slugify(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, "")
        .replace(/[\s_]+/g, "-")
        .replace(/-+/g, "-");
}

function updateCharCount(frm, fieldname, limit) {
    var val = frm.doc[fieldname] || "";
    var count = val.length;
    var color = count > limit ? "red" : count > limit * 0.85 ? "orange" : "green";
    frm.set_df_property(
        fieldname,
        "description",
        `<span style="color:${color}">${count}/${limit} characters</span>`
    );
}
