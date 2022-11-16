using JSON, DataFrames, Parquet

##

const rawdir = joinpath("..", "data", "raw")

const prodir = joinpath("..", "data", "pro")

##

function readpage(fn::String)::Dict
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
    df[!,"workout"] = 1:L
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
        df[!,k] .= v
    end
    return df
end

arrangepage(fn::String)::DataFrame = fn |> readpage |> arrangepage

## read, arrange, concatenate, and write all at once

write_parquet(
    joinpath(
        prodir,
        "arranged.parquet"
    ),
    vcat(
        map(
            arrangepage,
            readdir(
                rawdir,
                join=true
            )
        )...
    )
)

