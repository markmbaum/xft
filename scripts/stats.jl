using CSV, Parquet, DataFrames, StatsBase, HypothesisTests

##

const prodir = joinpath("..", "data", "pro")

##

xft = read_parquet(joinpath(prodir, "cleaned.parquet")) |> DataFrame

##

function corr(x, y)
    #compute correlation on rank indices, excluding missing values
    b = (!ismissing).(x) .& (!ismissing).(y)
    rx = x[b] |> tiedrank
    ry = y[b] |> tiedrank
    t = CorrelationTest(rx, ry)
    #correlation coefficient, p value, and number of samples
    c = t.r |> Float32
    p = pvalue(t) |> Float32
    N = sum(b) |> Int32
    return (c, p, N)
end

##

df = combine(
    groupby(
        xft,
        [:year, :competitionType, :divisionName, :workoutName]
    ),
    :workoutNumber => first => :workoutNumber,
    :divisionNumber => first => :divisionNumber,
    :competitionDivision => first => :competitionDivision,
    [:workoutRank, :height] => ((r,h) -> [corr(r,h)]) => [:c_height, :p_height, :N_height],
    [:workoutRank, :age] => ((r,a) -> [corr(r,a)]) => [:c_age, :p_age, :N_age],
    nrow
)

CSV.write(joinpath(prodir, "workout_statistics.csv"), df)

##

df = combine(
    groupby(
        unique(
            xft,
            [
                :year,
                :competitionType,
                :divisionName,
                :competitorName
            ]
        ),
        [:year, :competitionType, :divisionName]
    ),
    :divisionNumber => first => :divisionNumber,
    :competitionDivision => first => :competitionDivision,
    :height => median ∘ skipmissing => :medianHeight,
    :height => mean ∘ skipmissing => :meanHeight,
    :height => maximum ∘ skipmissing => :maxHeight,
    :height => minimum ∘ skipmissing => :minHeight,
    :height => std ∘ skipmissing => :stdHeight,
    [:overallRank, :height] => ((r,h) -> [corr(r,h)]) => [:c_height, :p_height, :N_height],
    [:overallRank, :age] => ((r,a) -> [corr(r,a)]) => [:c_age, :p_age, :N_age],
    :age => median ∘ skipmissing => :medianAge,
    :age => mean ∘ skipmissing => :meanAge,
    :age => maximum ∘ skipmissing => :maxAge,
    :age => minimum ∘ skipmissing => :minAge,
    :age => std ∘ skipmissing => :stdAge,
    nrow
)

CSV.write(joinpath(prodir, "competition_statistics.csv"), df)

##