"""
This script reads downloaded json files and puts them together into tables.
It produces the first stage of tabular data for all athlete results in the file:
    data/raw/athletes.parquet
It also produces the control table
    data/raw/controls.csv
which is mainly useful for checking workout numbers, names, order, etc. as it exist in the database.
"""

using DrWatson
@quickactivate "XFT"
using JSON, DataFrames, Parquet, CSV

##

const rawdir = datadir("raw")

const prodir = datadir("processed")

const cleandir = datadir("clean")

##

function readjson(fn::String)::Dict
    open(fn, "r") do f
        read(f) |> String |> JSON.parse
    end
end

function tabulaterow(row::Dict)::DataFrame
    #get the top level overall rank and score
    p = Dict(k=>row[k] for k ∈ ["overallRank", "overallScore"])
    #pull out the entrant parameters, excluding the picture name
    for (k,v) ∈ row["entrant"]
        if k != "profilePicS3key"
            p[k] = v
        end
    end
    #pull out the scores parameters, creating a new row for each
    scores = row["scores"]
    df = repeat(p |> DataFrame, length(scores))
    df[!,"workoutNumber"] = map(s -> s["ordinal"], scores) #the workout number is called "ordinal"
    for c ∈ ("rank", "score", "scoreDisplay", "valid")
        newcol = "workout" * uppercasefirst(c)
        df[!,newcol] = map(s -> s[c], scores)
    end
    return df
end

function tabulatepage(data::Dict)::DataFrame
    #personal info and scores/rankings
    df = vcat(map(tabulaterow, data["leaderboardRows"])...)
    #competition information
    for (k,v) ∈ data["competition"]
        df[!,(k == "division" ? "divisionNumber" : k)] .= v
    end
    return df
end

tabulatepage(fn::String)::DataFrame = fn |> readjson |> tabulatepage

function getdivisioncontrols(dir::String, comp::String, year::Int)
    data = readjson(joinpath(dir, "$(comp)_$(year)_controls.json"))
    controls = data["controls"]
    idx = findfirst(x -> x["config_name"] == "division", controls)
    divisions = Dict()
    if !ismissing(idx)
        for D ∈ controls[idx]["data"]
            v = D["value"]
            divisions[v] = Dict()
            divisions[v]["divisionName"] = D["display"]
            divisions[v]["workoutName"] = map(x -> x["display"], D["controls"][1]["data"][2:end])
            divisions[v]["workoutNumber"] = map(x -> x["sequence"], D["controls"][1]["data"][2:end])
        end
    end
    return divisions
end

## get all the file names

fnleaderboards = Vector{String}()
fncontrols = Vector{String}()
for (root, dirs, fns) ∈ walkdir(joinpath(rawdir, "competition-results"))
    for fn ∈ fns
        if occursin(".json", fn)
            if occursin("controls", fn)
                push!(fncontrols, joinpath(root, fn))
            else
                push!(fnleaderboards, joinpath(root, fn))
            end
        end
    end
end
sort!(fnleaderboards)
sort!(fncontrols)

## tabulate and concatenate all the leaderboard information

xft = reduce(vcat, map(tabulatepage, fnleaderboards))

##

write_parquet(joinpath(prodir, "competition_results.parquet"), xft)

##

df = combine(
    groupby(
        xft,
        [:year, :competitionType, :divisionNumber, :workoutNumber]
    ),
    nrow
)
filter!(r -> parse(Int, r.divisionNumber) < 3, df)
println(df)

## include workout and division names from control files

#this stopped working for the >2021 controls, which dont have the "division" field, not sure why
#nevertheless, it can be helpful to reference the incomplete table to check workout orders, names, etc

controls = DataFrame[]
for (comp,years) ∈ zip(["games", "open"], [2007:2021, 2011:2021])
    for year ∈ years
        dir = joinpath(rawdir, "competition-results", comp, year |> string)
        for (k,control) ∈ getdivisioncontrols(dir, comp, year)
            df = DataFrame(control)
            df[!,:year] .= year
            df[!,:divisionNumber] .= parse(Int, k)
            df[!,:competitionType] .= comp
            push!(controls, df)
        end
    end
end

CSV.write(joinpath(prodir, "controls.csv"), reduce(vcat, controls))

##
