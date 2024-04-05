import sys
from os.path import join
import pymc as pm

sys.path.append("modules")
import load_xft
import rank_models

cleandir = join("..", "data", "clean")

xft = load_xft.load_competition_results(
    join(cleandir, "competition_results.parquet"), 500
)
xft.sort_index(inplace=True)

for k, _ in xft.groupby(level=[0, 1]):
    model = rank_models.setup_comp_regression(xft, k[0], k[1])
    with model:
        post = pm.sample(
            cores=16, chains=16, tune=2_000, draws=2_000, target_accept=0.925
        ).posterior
    for v in post.data_vars:
        post[v] = post[v].astype("float32")
    for c in post.coords:
        post[c] = post.coords[c].values.astype("int32")
    post.to_netcdf(
        join(
            f"../model-results/competition-regressions/{k[0]}_{k[1]}.nc"
        )
    )
