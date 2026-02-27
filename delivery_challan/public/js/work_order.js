// Copyright (c) 2026, nts and contributors
// For license information, please see license.txt

nts.ui.form.on("Work Order", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Completed" && frm.doc.status !== "Closed") {
            frm.add_custom_button(__("Create DC"), function () {
                nts.model.with_doctype("Delivery Challan", function () {
                    let dc = nts.model.get_new_doc("Delivery Challan");
                    dc.company = frm.doc.company;

                    let items = [];
                    if (frm.doc.required_items && frm.doc.required_items.length > 0) {
                        frm.doc.required_items.forEach(item => {
                            items.push({
                                item_code: item.item_code,
                                uom: item.stock_uom,
                                description: item.description,
                                qty: item.required_qty,
                                work_order: frm.doc.name,
                                production_item: frm.doc.production_item,
                                production_qty: frm.doc.qty
                            });
                        });
                    }

                    dc.items = items;
                    nts.set_route("Form", "Delivery Challan", dc.name);
                });
            }).addClass("btn-primary");
        }
    }
});
