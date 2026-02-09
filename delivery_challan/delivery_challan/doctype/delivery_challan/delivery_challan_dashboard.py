# Copyright (c) 2026, nts and contributors
# For license information, please see license.txt

from nts import _

def get_data():
	return {
		"heatmap": True,
		"heatmap_message": _("This is based on the posting date of delivery challans"),
		"fieldname": "supplier",
		"transactions": [
			{
				"label": _("Material Movement"),
				"items": ["Stock Entry"]
			}
		]
	}
