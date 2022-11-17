using JSON, DataFrames, Parquet

##

const rawdir = joinpath("..", "data", "raw")

const prodir = joinpath("..", "data", "pro")

##

function readjson(fn::String)::Dict
    open(fn, "r") do f
        read(f) |> String |> JSON.parse
    end
end

function arrangerow(row::Dict)::DataFrame
    p = Dict(k=>row[k] for k ∈ ["overallRank", "overallScore"])
    for (k,v) ∈ row["entrant"]
        if k != "profilePicS3key"
            p[k] = v
        end
    end
    L = length(row["scores"])
    df = repeat(p |> DataFrame, L)
    df[!,"workoutNumber"] = 1:L
    for c ∈ ("rank", "score", "valid")
        df[!,c] = map(s -> s[c], row["scores"])
    end
    return df
end

function arrangepage(data::Dict)::DataFrame
    #personal info and scores/rankings
    df = vcat(map(arrangerow, data["leaderboardRows"])...)
    #competition information
    for (k,v) ∈ data["competition"]
        df[!,(k == "division" ? "divisionNumber" : k)] .= v
    end
    return df
end

arrangepage(fn::String)::DataFrame = fn |> readjson |> arrangepage

function getdivisioncontrols(comp::String, year::Int)
    data = readjson(joinpath(rawdir, "$(comp)_$(year)_controls.json"))
    idx = findfirst(x -> x["config_name"] == "division", data["controls"])
    divisions = Dict()
    for D ∈ data["controls"][idx]["data"]
        v = D["value"]
        divisions[v] = Dict()
        divisions[v]["divisionName"] = D["display"]
        divisions[v]["workoutNames"] = map(x -> x["display"], D["controls"][1]["data"][2:end])
    end
    return divisions
end

## read, arrange, and concatenate all the leaderboard information

xft = vcat(
    map(
        arrangepage,
        filter!(
            fn -> !occursin("controls", fn),
            readdir(
                rawdir,
                join=true
            )
        )
    )...
)

## include workout and division names from control files

controls = Dict(
    "games" => Dict(),
    "open" => Dict()
)
for year ∈ 2007:2022
    controls["games"][year] = getdivisioncontrols("games", year)
end
for year ∈ 2011:2022
    controls["open"][year] = getdivisioncontrols("open", year)
end

##

cols = [:competitionType, :year, :divisionNumber, :workoutNumber]
transform!(
    xft,
    cols => ByRow((c,y,d,w) -> controls[c][y][d]["workoutNames"][w]) => "workoutName",
    cols => ByRow((c,y,d,_) -> controls[c][y][d]["divisionName"]) => "divisionName"
)

##

write_parquet(
    joinpath(
        prodir,
        "arranged.parquet"
    ),
    xft
)
