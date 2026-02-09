// Copyright (c) 2026, nts and contributors
// For license information, please see license.txt

nts.query_reports["Delivery Challan Summary"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: nts.defaults.get_user_default("Company"),
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: nts.datetime.add_months(nts.datetime.get_today(), -1)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: nts.datetime.get_today()
        },
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier"
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nSent\nPartially Received\nReceived"
        },
        {
            fieldname: "from_warehouse",
            label: __("From Warehouse"),
            fieldtype: "Link",
            options: "Warehouse"
        }
    ]
};
