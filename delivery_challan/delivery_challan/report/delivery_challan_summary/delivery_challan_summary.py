# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

import nts
from nts import _
from nts.utils import getdate, date_diff, today


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	
	return columns, data


def get_columns():
	return [
		{
			"label": _("Delivery Challan"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Delivery Challan",
			"width": 140
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150
		},
		{
			"label": _("Supplier Name"),
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("From Warehouse"),
			"fieldname": "from_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150
		},
		{
			"label": _("To Warehouse"),
			"fieldname": "to_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150
		},
		{
			"label": _("Total Items"),
			"fieldname": "total_items",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Total Qty"),
			"fieldname": "total_qty",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": _("Sent Date"),
			"fieldname": "sent_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Received Date"),
			"fieldname": "received_date",
			"fieldtype": "Date",
			"width": 110
		},
		{
			"label": _("Expected Return Date"),
			"fieldname": "expected_return_date",
			"fieldtype": "Date",
			"width": 110
		},
		{
			"label": _("Is Overdue"),
			"fieldname": "is_overdue",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": _("Days Outside"),
			"fieldname": "days_outside",
			"fieldtype": "Int",
			"width": 110
		},
		{
			"label": _("Current Days"),
			"fieldname": "current_days",
			"fieldtype": "Int",
			"width": 110
		}
	]


def get_data(filters):
	conditions = get_conditions(filters)
	
	data = nts.db.sql("""
		SELECT 
			dc.name,
			dc.posting_date,
			dc.supplier,
			dc.supplier_name,
			dc.status,
			dc.from_warehouse,
			dc.to_warehouse,
			dc.sent_date,
			dc.received_date,
			dc.expected_return_date,
			dc.days_outside,
			(SELECT COUNT(*) FROM `tabDelivery Challan Item` dci WHERE dci.parent = dc.name) as total_items,
			(SELECT SUM(dci.qty) FROM `tabDelivery Challan Item` dci WHERE dci.parent = dc.name) as total_qty
		FROM `tabDelivery Challan` dc
		WHERE dc.docstatus = 1
		{conditions}
		ORDER BY dc.posting_date DESC, dc.name DESC
	""".format(conditions=conditions), filters, as_dict=1)
	
	# Calculate current days for pending challans and overdue status
	for row in data:
		if row.status in ["Sent", "Partially Received"]:
			if row.sent_date:
				row.current_days = date_diff(today(), getdate(row.sent_date))
			
			if row.expected_return_date and getdate(today()) > getdate(row.expected_return_date):
				row.is_overdue = "Yes"
			else:
				row.is_overdue = "No"
		else:
			row.current_days = row.days_outside or 0
			row.is_overdue = "No"
	
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("dc.posting_date >= %(from_date)s")
	
	if filters.get("to_date"):
		conditions.append("dc.posting_date <= %(to_date)s")
	
	if filters.get("supplier"):
		conditions.append("dc.supplier = %(supplier)s")
	
	if filters.get("status"):
		conditions.append("dc.status = %(status)s")
	
	if filters.get("company"):
		conditions.append("dc.company = %(company)s")
	
	if filters.get("from_warehouse"):
		conditions.append("dc.from_warehouse = %(from_warehouse)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""
