# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

import nts
from nts import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	
	return columns, data, None, chart


def get_columns():
	return [
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 200
		},
		{
			"label": _("Supplier Name"),
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Total Challans"),
			"fieldname": "total_challans",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": _("Received Challans"),
			"fieldname": "received_challans",
			"fieldtype": "Int",
			"width": 130
		},
		{
			"label": _("Pending Challans"),
			"fieldname": "pending_challans",
			"fieldtype": "Int",
			"width": 130
		},
		{
			"label": _("Avg Days Outside"),
			"fieldname": "avg_days",
			"fieldtype": "Float",
			"precision": 1,
			"width": 130
		},
		{
			"label": _("Min Days"),
			"fieldname": "min_days",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Max Days"),
			"fieldname": "max_days",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Total Items Sent"),
			"fieldname": "total_items",
			"fieldtype": "Int",
			"width": 120
		}
	]


def get_data(filters):
	conditions = get_conditions(filters)
	
	data = nts.db.sql("""
		SELECT 
			dc.supplier,
			dc.supplier_name,
			COUNT(dc.name) as total_challans,
			SUM(CASE WHEN dc.status = 'Received' THEN 1 ELSE 0 END) as received_challans,
			SUM(CASE WHEN dc.status IN ('Sent', 'Partially Received') THEN 1 ELSE 0 END) as pending_challans,
			AVG(CASE WHEN dc.days_outside > 0 THEN dc.days_outside ELSE NULL END) as avg_days,
			MIN(CASE WHEN dc.days_outside > 0 THEN dc.days_outside ELSE NULL END) as min_days,
			MAX(CASE WHEN dc.days_outside > 0 THEN dc.days_outside ELSE NULL END) as max_days,
			(SELECT SUM(dci.qty) FROM `tabDelivery Challan Item` dci WHERE dci.parent = dc.name) as total_items
		FROM `tabDelivery Challan` dc
		WHERE dc.docstatus = 1
		{conditions}
		GROUP BY dc.supplier, dc.supplier_name
		ORDER BY avg_days DESC
	""".format(conditions=conditions), filters, as_dict=1)
	
	# Calculate total items for each supplier
	for row in data:
		items = nts.db.sql("""
			SELECT SUM(dci.qty) as total
			FROM `tabDelivery Challan Item` dci
			INNER JOIN `tabDelivery Challan` dc ON dc.name = dci.parent
			WHERE dc.supplier = %s AND dc.docstatus = 1
		""", row.supplier, as_dict=1)
		row.total_items = items[0].total if items and items[0].total else 0
	
	return data


def get_conditions(filters):
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("dc.posting_date >= %(from_date)s")
	
	if filters.get("to_date"):
		conditions.append("dc.posting_date <= %(to_date)s")
	
	if filters.get("supplier"):
		conditions.append("dc.supplier = %(supplier)s")
	
	if filters.get("company"):
		conditions.append("dc.company = %(company)s")
	
	return " AND " + " AND ".join(conditions) if conditions else ""


def get_chart_data(data):
	if not data:
		return None
	
	labels = [row.supplier_name or row.supplier for row in data[:10]]
	values = [row.avg_days or 0 for row in data[:10]]
	
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Avg Days Outside"),
					"values": values
				}
			]
		},
		"type": "bar",
		"colors": ["#5e64ff"]
	}
