import pymc as pm
import numpy as np
import statsmodels.api as sm
from pandas import DataFrame
import torch
from torch import nn
from torch import optim

import matplotlib.pyplot as plt

from typing import Optional, Tuple


def setup_division_regression(
    xft: DataFrame,
    year: int,
    competitionType: str,
    workoutNumber: int,
    divisionName: str,
) -> pm.Model:
    df = xft.xs(key=(year, competitionType, workoutNumber, divisionName))
    df = df[["r", "h", "w", "a"]].dropna()
    assert len(df) > 0, "no records found"
    print(f"{len(df):5} records")

    with pm.Model() as model:

        X = pm.ConstantData("X", df[["h", "w", "a"]].values)
        y = pm.ConstantData("y", df["r"].values)

        a = pm.Normal("a")
        b = pm.Normal("b", sigma=1, shape=3)

        mu = a + pm.math.dot(X, b)
        sigma = pm.Exponential("sigma", scale=1)

        pm.Normal("obs", mu=mu, sigma=sigma, observed=y)

    return model


def correlated_effects(ndiv, X, y):

    with pm.Model() as model:

        M = pm.Normal("mu", shape=3)
        chol, corr, stds = pm.LKJCholeskyCov(
            "LKJ", eta=2, n=3, sd_dist=pm.HalfNormal.dist(sigma=1.0, size=3)
        )
        pm.Deterministic("height-weight correlation", corr[0, 1])
        pm.Deterministic("height-age correlation", corr[0, 2])
        pm.Deterministic("weight-age correlation", corr[1, 2])
        pm.Deterministic("stds", stds)

        # non-centered correlated slopes/effects
        B_ = pm.Normal("B_", shape=(ndiv, 3))
        B = pm.Deterministic("B", M + pm.math.dot(chol, B_.T).T)

        # independent intercepts and standard deviations
        a = pm.Normal("intercept", shape=ndiv)
        sigma = pm.Exponential("sigma", scale=1, shape=ndiv)

        for i, d in enumerate(X):
            b = pm.Deterministic(f"b {d}", B[i, :])
            mu = pm.Deterministic(f"mu {d}", a[i] + pm.math.dot(X[d], b))
            pm.Normal(f"obs {d}", mu=mu, sigma=sigma[i], observed=y[d])

    return model


def setup_event_regression(
    xft: DataFrame,
    year: int,
    competitionType: str,
    workoutNumber: int,
    divisions: Optional[Tuple[str]] = None,
    *,
    silent: bool = False,
) -> pm.Model:

    df = xft.xs(key=(year, competitionType, workoutNumber))
    df = df[["r", "h", "w", "a"]].dropna()
    assert len(df) > 0, "no records found"

    # assemble a dictionary of inputs and outputs keyed by division names
    X = {}
    y = {}
    for d, g in df.groupby(level=0):
        if (divisions is None) or (d in divisions):
            if not silent:
                print(f"{d:15} {len(g):5} records")
            X[d] = g[["h", "w", "a"]].values
            y[d] = g["r"].values
    ndiv = len(X)

    return correlated_effects(ndiv, X, y)


def setup_comp_regression(
    xft: DataFrame,
    year: int,
    competitionType: str,
    *,
    silent: bool = False,
) -> pm.Model:

    df = xft.xs(key=(year, competitionType)).droplevel(0).drop_duplicates(
        subset=("gender", "height", "weight", "age", "o")
    )
    df = df[["o", "h", "w", "a"]].dropna()
    assert len(df) > 0, "no records found"

    # assemble a dictionary of inputs and outputs keyed by division names
    X = {}
    y = {}
    for d, g in df.groupby(level=0):
        if not silent:
            print(f"{d:15} {len(g):5} records")
        X[d] = g[["h", "w", "a"]].values
        y[d] = g["o"].values
    ndiv = len(X)

    return correlated_effects(ndiv, X, y)


class LinearRegression(nn.Module):
    def __init__(self, nfeature):
        super().__init__()
        self.beta = nn.Linear(nfeature, 1, bias=True)

    def forward(self, X):
        return self.beta(X)


class GaussianNoise(nn.Module):

    def __init__(self, sigma=0.005):
        super(GaussianNoise, self).__init__()
        self.sigma = sigma

    def forward(self, x):
        if self.training:
            noise = torch.randn_like(x) * self.sigma
            return x + noise
        return x


def semantic_block(ninput, noutput, *, noise=0.01, dropout=0.01):
    return nn.Sequential(
        nn.Linear(ninput, noutput),
        nn.ELU(),
        GaussianNoise(noise),
        nn.Dropout(dropout),
    )


class SemanticModel(nn.Module):
    def __init__(self, nemb, *, nlayer=1, nhidden=32, noise=0.01, dropout=0.01):
        super().__init__()
        assert nlayer >= 0
        if nlayer == 0:
            self.semantic_effects = nn.Linear(nemb, 3)
        elif nlayer == 1:
            self.semantic_effects = nn.Sequential(
                semantic_block(nemb, nhidden, noise=noise, dropout=dropout),
                nn.Linear(nhidden, 3),
            )
        else:
            blocks = [semantic_block(nemb, nhidden, noise=noise, dropout=dropout)]
            for _ in range(1, nlayer):
                blocks.append(
                    semantic_block(nhidden, nhidden, noise=noise, dropout=dropout)
                )
            blocks.append(nn.Linear(nhidden, 3))
            self.semantic_effects = nn.Sequential(*blocks)

    def forward(self, E, X):
        B = self.semantic_effects(E)
        y = [
            [torch.matmul(B[i, :], X[i][j]) for j in range(len(X[i]))]
            for i in range(len(X))
        ]
        return y


class NestedListLoss(nn.Module):
    def __init__(self):
        super(NestedListLoss, self).__init__()

    def forward(self, input_list, target_list):
        # Ensure that input_list and target_list are lists of tensors of the same length
        if len(input_list) != len(target_list):
            raise ValueError("Input and target lists must have the same length")

        total_loss = 0.0
        ngroup = len(input_list)
        for input_tensors, target_tensors in zip(input_list, target_list):
            for input_tensor, target_tensor in zip(input_tensors, target_tensors):
                loss = nn.functional.l1_loss(input_tensor, target_tensor)
                total_loss += loss / (ngroup * len(input_tensors))

        # Average the total loss by the number of elements in the list
        return total_loss


def semantic_effects(model, E):
    return model.semantic_effects.forward(E).detach().numpy()


def direct_regressions(X, Y):
    regs = []
    for i in range(len(Y)):
        regs.append([])
        for j in range(len(Y[i])):
            x = X[i][j].detach().numpy().astype(np.float32).T
            y = Y[i][j].detach().numpy().astype(np.float32)
            regs[-1].append(sm.OLS(y, x).fit().params)
    return regs


def effect_differences(model, E, X, Y):
    effects = semantic_effects(model, E)
    regs = direct_regressions(X, Y)
    regs = np.stack([reg[0] for reg in regs])
    return np.abs(effects - regs).mean()


def fit_semantic_model(
    nemb,
    E_train,
    X_train,
    Y_train,
    E_valid=None,
    X_valid=None,
    Y_valid=None,
    *,
    nlayer=1,
    nhidden=32,
    weight_decay=0.0,
    noise=0.0,
    dropout=0.0,
    verbose=True,
    epochs=500,
    plot=False,
):
    if E_valid is None:
        assert X_valid is None and Y_valid is None
    model = SemanticModel(
        nemb, nlayer=nlayer, nhidden=nhidden, noise=noise, dropout=dropout
    )
    if verbose:
        total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"embedding length = {nemb}\nmodel parameters = {total_params}")
    optimizer = optim.Adam(model.parameters(), weight_decay=weight_decay)
    criterion = NestedListLoss()
    L_train = [criterion(model.forward(E_train, X_train), Y_train).item()]
    L_valid = []
    eff_dif = []
    if E_valid is not None:
        L_valid.append(criterion(model.forward(E_valid, X_valid), Y_valid).item())
        eff_dif.append(effect_differences(model, E_valid, X_valid, Y_valid))
    for epoch in range(epochs):
        optimizer.zero_grad()
        outputs = model(E_train, X_train)
        loss = criterion(outputs, Y_train)
        loss.backward()
        optimizer.step()
        L_train.append(loss.item())
        if E_valid is not None:
            L_valid.append(criterion(model.forward(E_valid, X_valid), Y_valid).item())
            if epoch % 20 == 0:
                eff_dif.append(effect_differences(model, E_valid, X_valid, Y_valid))
        if verbose and ((epoch + 1) % 100 == 0):
            print(f"step {epoch+1}\n  train loss = {np.mean(L_train[-8:])}")
            if L_valid:
                print(f"  valid loss = {np.mean(L_valid[-8:])}")
                print(f"  mean abs effect difference = {eff_dif[-1]}")
    if plot:
        fig, axs = plt.subplots(1, 2, figsize=(8, 4))
        axs[0].plot(L_train, label="training loss")
        if L_valid:
            axs[0].plot(L_valid, label="validation loss")
        axs[0].set_xlabel("epoch")
        axs[0].set_ylabel("loss")
        axs[0].legend()
        axs[1].plot(
            np.arange(0, 20 * len(eff_dif), 20) + 1, eff_dif, ".-", linewidth=0.75
        )
        axs[1].set_xlabel("epoch")
        axs[1].set_ylabel("mean effect differences")
        fig.tight_layout()
    return model, criterion, np.array(L_train), np.array(L_valid), np.array(eff_dif)
