import pandas as pd


def generate_supply_chain_features(dataframe: pd.DataFrame):
    dataframe = dataframe.copy()

    # Generate lead_time when order and delivery dates are available
    order_date_column = _find_column(
        dataframe,
        ["order_date", "order date", "orderdate"]
    )

    delivery_date_column = _find_column(
        dataframe,
        ["delivery_date", "delivery date", "deliverydate"]
    )

    if order_date_column and delivery_date_column:

        order_dates = pd.to_datetime(
            dataframe[order_date_column],
            errors="coerce"
        )

        delivery_dates = pd.to_datetime(
            dataframe[delivery_date_column],
            errors="coerce"
        )

        dataframe["lead_time"] = (
            delivery_dates - order_dates
        ).dt.days

    # Generate cost_per_unit when total cost and quantity are available
    total_cost_column = _find_column(
        dataframe,
        ["total_cost", "total cost", "totalcost"]
    )

    quantity_column = _find_column(
        dataframe,
        ["quantity", "qty"]
    )

    if total_cost_column and quantity_column:

        quantity = dataframe[quantity_column]

        dataframe["cost_per_unit"] = (
            dataframe[total_cost_column]
            / quantity.replace(0, pd.NA)
        )

    return dataframe


def _find_column(dataframe: pd.DataFrame, possible_names):

    column_mapping = {
        str(column).lower().strip(): column
        for column in dataframe.columns
    }

    for name in possible_names:

        if name in column_mapping:
            return column_mapping[name]

    return None