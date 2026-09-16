import pandas as pd

from backend.services.sensitive_detector import (
    detect_sensitive_and_identifier_columns
)


data = {
    "customer_id": [101, 102, 103, 104, 105],
    "name": ["A", "B", "C", "D", "E"],
    "email": [
        "a@gmail.com",
        "b@gmail.com",
        "c@gmail.com",
        "d@gmail.com",
        "e@gmail.com"
    ],
    "age": [25, 30, 28, 35, 40],
    "salary": [40000, 50000, 45000, 60000, 70000],
    "city": ["Delhi", "Pune", "Mumbai", "Delhi", "Pune"]
}

dataframe = pd.DataFrame(data)

results = detect_sensitive_and_identifier_columns(dataframe)

for result in results:
    print(result)