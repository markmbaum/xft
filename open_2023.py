# %%

import pandas as pd
from pandas import read_csv, read_parquet
import matplotlib.pyplot as plt
from seaborn import *

plt.style.use('bmh')

# %%

df = read_csv('data/pro/workout_statistics.csv')
df = df[df.competitionType == 'open']
# %%

fig, ax = plt.subplots(1, 1, constrained_layout=True)
barplot(
    data=df[df.year == 2023],
    x='workoutName',
    y='c_height',
    hue='divisionName',
    width=0.6,
    edgecolor='k',
    ax=ax
)
ax.invert_yaxis()
ax.set_xlabel('2023 Open Workout')
ax.set_ylabel('Spearman Rank Correlation')
ax.set_title('Rank Correlation—Athlete Height & Workout Placement')
ax.get_legend().set_title('Division')
ax.axhline(0, color='k', linewidth=1, zorder=-1)
ax.grid(False)
fig.savefig('plots/open_2023_correlations.png', dpi=250)
plt.close(fig)

# %%

fig, ax = plt.subplots(1, 1, constrained_layout=True)
workouts = ['15.1a', '18.2a', '21.4', '23.2b']
barplot(
    data=df.loc[map(lambda x: x in workouts, df.workoutName)].sort_values(by='workoutName'),
    x='workoutName',
    y='c_height',
    hue='divisionName',
    width=0.6,
    edgecolor='k',
    ax=ax
)
ax.invert_yaxis()
ax.set_xlabel('Open Workout')
ax.set_xticklabels([a + '\n' + b for (a,b) in zip(workouts, ['Clean & Jerk', 'Clean', 'Complex', 'Thruster'])])
ax.set_ylabel('Spearman Rank Correlation')
ax.set_title('Rank Correlation—Athlete Height & Workout Placement')
leg = ax.get_legend()
leg.set_title('Division')
ax.axhline(0, color='k', linewidth=1, zorder=-1)
ax.grid(False)
fig.savefig('plots/open_max_lift_correlations.png', dpi=250)
plt.close(fig)

# %%

df = read_parquet('data/pro/cleaned.parquet')
df = df[(df.year == 2023) & (df.competitionType == 'open') & (df.divisionNumber < 3)]
df['height'] /= 0.3048
df = df[(df['height'] > 4.5) & (df['height'] < 7)]
labels=['1 - 250', '250 - 500', '500 - 1,000', '1,000 - 5,000', '5,000 - 10,000', '10,000 - 20,000']
df['rankGroup'] = pd.cut(
    df.workoutRank,
    [1, 250, 500, 1000, 5000, 10_000, 20_000],
    labels=labels
)
df['rankCode'] = df.rankGroup.cat.codes
df = df[df.rankCode >= 0]

workouts = sorted(df.workoutName.unique())
N = len(workouts)
fig, axs = plt.subplots(2, N, figsize=(12,7), constrained_layout=True, sharex=True)
for i in range(2):
    division = i + 1
    for j in range(N):
        workout = workouts[j]
        ax = axs[i,j]
        sl = df[(df.workoutName == workout) & (df.divisionNumber == division)].copy()
        lineplot(
            data=sl,
            x='rankCode',
            y='height',
            color=f'C{i}',
            errorbar='se',
            ax=ax
        )
        #regplot(
        #    data=sl,
        #    x='workoutRank',
        #    y='height',
        #    color='k',
        #    ci=False,
        #    scatter=False,
        #    line_kws=dict(linewidth=1.5),
        #    ax=ax
        #)
        ax.set_xlabel(None)
        ax.set_ylabel(None)
        ax.set_xlim(0, sl.rankCode.max())
        ax.set_xticks(sorted(sl.rankCode.unique()))
        if i == 0:
            ax.set_title(workout)
            ax.set_xticklabels([])
        else:
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
axs[0,0].set_ylabel("Average Men's Height [ft]")
axs[1,0].set_ylabel("Average Women's Height [ft]")
for j in range(4):
    axs[0,j].set_ylim(5.68, 5.90)
    axs[1,j].set_ylim(5.275, 5.6)
fig.supxlabel('Workout Rank/Placement')
fig.savefig('plots/open_2023_regplots', dpi=250)
plt.close(fig)
