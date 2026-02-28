### Delivery Challan

Delivery Challan generation for app

### Installation

You can install this app using the [bench](https://github.com/nts/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app delivery_challan
```

### Required Custom Fields (If Production Planning App is Separate)

If you are installing this on a site that already has the manufacturing/production planning app installed separately, you need to manually add the following Custom Field to the **Operation** DocType for this app to function fully:

- **DocType**: Operation
- **Label**: Follows Production Qty
- **Fieldname**: follows_production_qty (Important: must exactly match)
- **Fieldtype**: Check
- **Default**: 0
- **Description**: If checked, Subcontracting Delivery Challans will track supplier qty using Product Qty instead of RM Qty.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/delivery_challan
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
