# %%

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
ax.set_xlabel(None)
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
ax.set_xlabel(None)
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

workouts = sorted(df.workoutName.unique())
N = len(workouts)
fig, axs = plt.subplots(2, N, figsize=(12,6), constrained_layout=True, sharex=True, sharey=True)
for i in range(2):
    division = i + 1
    for j in range(N):
        workout = workouts[j]
        ax = axs[i,j]
        sl = df[(df.workoutName == workout) & (df.divisionNumber == division)]
        scatterplot(
            data=sl,
            x='workoutRank',
            y='height',
            color=f'C{i}',
            alpha=0.5,
            ax=ax
        )
        regplot(
            data=sl,
            x='workoutRank',
            y='height',
            color='k',
            ci=False,
            scatter=False,
            line_kws=dict(linewidth=1),
            ax=ax
        )
        ax.set_xlabel(None)
        if i == 0:
            ax.set_title(workout)            
axs[0,0].set_ylabel("Women's Height [meters]")
axs[1,0].set_ylabel("Men's Height [meters]")
fig.supxlabel('Workout Rank/Placement')
fig.savefig('plots/open_2023_regplots', dpi=250)
plt.close(fig)
