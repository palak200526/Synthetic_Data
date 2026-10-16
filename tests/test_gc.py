import pandas as pd, numpy as np
from backend.generation.gaussian_copula import GaussianCopulaGenerator

df = pd.DataFrame({
    "id": [f"A{i}" for i in range(500)],
    "age": np.random.randint(18, 70, 500),
    "salary": np.random.normal(50000, 10000, 500),
    "city": np.random.choice(["Delhi", "Pune", "Goa", None], 500),
})
g = GaussianCopulaGenerator().fit(df, identifier_columns=["id"])
print(g.generate(10))
print(g.generate(10).dtypes)