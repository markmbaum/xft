using Parquet, DataFrames, StatsBase

##

const prodir = joinpath("..", "data", "pro")

##

xft = read_parquet(joinpath(prodir, "arranged.parquet")) |> DataFrame

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
        :workoutValid,
        :firstName,
        :lastName
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

xft[!,:gender] = map(x -> first(x) == 'M' ? true : false, xft.gender)

xft[!,:scaled] = parse.(Bool, xft.scaled)

xft[!,:height] = map(xft.height) do h
    if ismissing(h) || isempty(h)
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

xft[!,:height] = map(xft.height) do h
    if ismissing(h)
        missing
    elseif 1 < h < 2.5
        h
    elseif h > 12.5
        h / 1f1
    elseif 3 <= h <= 6
        h * 3.93f1/1f2
    elseif 0.5 < h < 1
        h * 1f2/3.93f1
    else
        missing
    end
end

xft[!,:weight] = map(xft.weight) do w
    if ismissing(w) || ((w > 300) | (w ≈ 0.454) | (w ≈ 1))
        missing
    else
        w
    end
end

## try to fill missing height cells

name2height = combine(
    groupby(xft, :competitorName),
    :height => (h -> mean(skipmissing(h))) => :height
)

name2height = Dict(zip(
    name2height.competitorName,
    replace(name2height.height, NaN => missing)
))

xft[!,:height] = map(name -> name2height[name], xft.competitorName)

##

write_parquet(
    joinpath(
        prodir,
        "cleaned.parquet"
    ),
    xft
)

##