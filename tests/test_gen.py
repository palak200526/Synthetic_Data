import pandas as pd, numpy as np
from backend.generation.ctgan import CTGANGenerator
from backend.generation.tvae import TVAEGenerator

df = pd.DataFrame({
    "id": [f"A{i}" for i in range(500)],
    "age": np.random.randint(18, 70, 500),
    "salary": np.random.normal(50000, 10000, 500),
    "city": np.random.choice(["Delhi", "Pune", "Goa", None], 500),
})

for G in (CTGANGenerator, TVAEGenerator):
    g = G(epochs=5).fit(df, identifier_columns=["id"],
                        progress_callback=lambda e, t: print(e, t))
    print(g.generate(10))