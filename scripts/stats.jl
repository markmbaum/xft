using CSV, Parquet, DataFrames, StatsBase, HypothesisTests

##

const prodir = joinpath("..", "data", "pro")

##

xft = read_parquet(joinpath(prodir, "cleaned.parquet")) |> DataFrame

##

function corr(x, y, nmax=Inf)
    #compute correlation on rank indices, excluding missing values
    b = (x .|> !ismissing) .& (y .|> !ismissing)
    N = sum(b)
    x = x[b]
    y = y[b]    
    if N > nmax
        x = x[1:nmax]
        y = y[1:nmax]
        N = nmax
    end
    t = CorrelationTest(tiedrank(x), tiedrank(y))
    #correlation coefficient, p value, and number of samples
    c = t.r |> Float32
    p = pvalue(t) |> Float32
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
    [:workoutRank, :age]    => ((r,a) -> [corr(r,a)]) => [:c_age, :p_age, :N_age],
    nrow
)

CSV.write(
    joinpath(
        prodir,
        "workout_statistics.csv"
    ),
    df
)


##

g = groupby(
    filter(r -> (r.competitionType == "open") & (r.divisionNumber < 3), xft), 
    [:year, :divisionName, :workoutName]
)

df = combine(g, :height => (h -> h .|> !ismissing |> sum) => :nheight)

nmax = 25:25:maximum(df.nheight)

for i ∈ eachindex(nmax)
    c = combine(g, [:workoutRank, :height] => ((r,h) -> [corr(r,h,nmax[i])]) => [:c_height, :p_height, :N_height])
    b = c[!,:N_height] .< nmax[i] 
    for col ∈ [:c_height, :p_height, :N_height]
        s = string(col)*'_'*string(nmax[i])
        v = c[!,col] |> allowmissing
        v[b] .= missing
        df[!,s] = v
    end
end

CSV.write(
    joinpath(
        prodir,
        "workout_height_correlation_CV.csv"
    ),
    df
)

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
    [:overallRank, :age]    => ((r,a) -> [corr(r,a)]) => [:c_age, :p_age, :N_age],
    :age => median ∘ skipmissing => :medianAge,
    :age => mean ∘ skipmissing => :meanAge,
    :age => maximum ∘ skipmissing => :maxAge,
    :age => minimum ∘ skipmissing => :minAge,
    :age => std ∘ skipmissing => :stdAge,
    nrow
)

CSV.write(
    joinpath(
        prodir,
        "competition_statistics.csv"
    ),
    df
)

##