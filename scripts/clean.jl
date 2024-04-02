"""
This script takes the raw tabulated data at:
    data/raw/athletes.parquet
and cleans it up into a slimmer table with only relevant columns and fewer unit problems, writing the cleaned version to:
    data/pro/athletes.parquet
"""

using DrWatson
@quickactivate "XFT"
using Parquet, CSV, DataFrames, StatsBase

##

const rawdir = datadir("raw")

const prodir = datadir("processed")

const cleandir = datadir("clean")

##

function fillbyname!(df::DataFrame, col::Symbol)::Nothing
    X = combine(
        groupby(df, :competitorName),
        col => (h -> mean(skipmissing(h))) => col
    )
    mapper = Dict(zip(
        X.competitorName,
        replace(X[!,col], NaN => missing)
    ))
    df[!,col] = map(name -> mapper[name], xft.competitorName)
    nothing
end

## read the first stage of athlete data

xft = read_parquet(joinpath(prodir, "competition_results.parquet")) |> DataFrame

##

divisions = CSV.File(joinpath(rawdir, "divisions.csv")) |> DataFrame

divisions = Dict(zip(divisions.divisionNumber, divisions.divisionName))

##

#unwanted columns
select!(
    xft,
    Not([
        :postCompStatus,
        :teamCaptain,
        :inSubCat,
        :fittestIn,
        :divisionId,
        :firstName,
        :lastName,
    ])
)
for prefix ∈ ["affiliate", "country", "region"]
    select!(xft, Cols(col -> !startswith(col, prefix)))
end

#integer columns
for col ∈ [
        :age,
        :competitorId,
        :overallRank,
        :overallScore,
        :workoutNumber,
        :workoutRank,
        :workoutScore,
        :competitionId,
        :year,
        :divisionNumber
    ]
    xft[!,col] = map(xft[!,col]) do x
        if ismissing(x)
            missing
        elseif typeof(x) <: Real
            convert(Int32, x)
        elseif typeof(x) <: AbstractString
            try
                parse(Int32, x)
            catch e
                missing
            end
        end
    end
end

## division labels

xft[!,:divisionName] = map(n -> String(divisions[n]), xft.divisionNumber)

##

#age group or individual flag
xft[!,:individual] = map(d -> d <= 2 ? true : false, xft.divisionNumber)

#unwanted divisions (have to exclude adaptive athletes)
filter!(:divisionNumber => x -> x ∉ 20:35, xft)

xft[!,:gender] = map(x -> first(x) == 'M' ? true : false, xft.gender)

#exclude the scaled divisions
xft[!,:scaled] = parse.(Bool, xft.scaled)
filter!(:scaled => s -> !(s), xft)

xft[!,:height] = map(xft.height) do h
    if ismissing(h) | isempty(h)
        missing
    elseif occursin("cm", h)
        parse(Float32, filter(isnumeric, h)) / 1f2
    elseif occursin("in", h)
        parse(Float32, filter(isnumeric, h)) / 3.93f1
    end
end

xft[!,:weight] = map(xft.weight) do w
    if ismissing(w) || isempty(w)
        missing
    elseif occursin("lb", w)
        parse(Float32, filter(isnumeric, w)) * 0.454f0
    elseif occursin("kg", w)
        parse(Float32, filter(isnumeric, w))
    end
end

xft[!,:age] = map(xft.age) do a
    if ismissing(a) || isempty(a)
        missing
    elseif (a == 0)
        missing
    else
        a
    end
end

for col ∈ [:status, :competitorName]
    xft[!,col] = map(xft[!,col]) do x
        if ismissing(x) || isempty(x)
            missing
        else
            x |> string
        end
    end
end

##

xft[!,:age] = map(xft.age) do a
    if ismissing(a) || (a < 14) | (a > 100) #there are no divisions for under 14 year olds
        missing
    else
        a
    end
end

#probably data entry errors, physically quite implausible
xft[!,:height] = map(xft.height) do h
    if ismissing(h) || (h < 1.2) | (h > 2.13)
        missing
    else
        h
    end
end

#probably data entry errors, physically quite implausible
xft[!,:weight] = map(xft.weight) do w
    if ismissing(w) || (w < 35) | (w > 150)
        missing
    else
        w
    end
end

xft[!,:workoutValid] = map(xft.workoutValid) do v
    if ismissing(v) | isempty(v)
        missing
    else
        parse(Bool, v)
    end
end

## try to fill missing height and weight cells by averaging over existing participant values

fillbyname!(xft, :height)
fillbyname!(xft, :weight)

##

#workout 8 in the 2020 is just a tabulation after stage 1, not a real workout
filter!(r -> (r.year != 2020) | (r.workoutNumber != 8), xft)

##

write_parquet(joinpath(cleandir, "competition_results.parquet"), xft)

##
