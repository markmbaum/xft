# %%

from pandas import read_csv
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
    ax=ax
)
ax.invert_yaxis()
ax.set_xlabel(None)
ax.set_ylabel('Spearman Rank Correlation')
ax.set_title('Rank Correlation—Athlete Height & Workout Placement')
ax.get_legend().set_title('Division')
ax.axhline(0, color='k', alpha=0.5, zorder=-1)
fig.savefig('plots/open_2023_tentative.png', dpi=250)
plt.close(fig)

# %%

fig, ax = plt.subplots(1, 1, constrained_layout=True)
workouts = ['15.1a', '18.2a', '21.4', '23.2b']
barplot(
    data=df.loc[map(lambda x: x in workouts, df.workoutName)].sort_values(by='workoutName'),
    x='workoutName',
    y='c_height',
    hue='divisionName',
    ax=ax
)
ax.invert_yaxis()
ax.set_xlabel(None)
ax.set_xticklabels([a + '\n' + b for (a,b) in zip(workouts, ['Clean & Jerk', 'Clean', 'Complex', 'Thruster'])])
ax.set_ylabel('Spearman Rank Correlation')
ax.set_title('Rank Correlation—Athlete Height & Workout Placement')
leg = ax.get_legend()
leg.set_title('Division')
ax.axhline(0, color='k', alpha=0.5, zorder=-1)
fig.savefig('plots/open_max_lift_comparisons.png', dpi=250)
plt.close(fig)
