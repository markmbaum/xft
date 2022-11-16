using URIs, HTTP, JSON
using Base.Threads: @threads

##

const rawdir = joinpath("..", "data", "raw")

##

function makeurl(comp::String, year::Int, query::Dict=Dict())::URI
    URI(
        scheme="https",
        host="games.crossfit.com",
        path="/api/competitions/v2/competitions/$comp/$year/leaderboards",
        query=query
    )
end

function getpage(comp::String, year::Int, query::Dict=Dict())::Dict
    HTTP.get(makeurl(comp, year, query)).body |> String |> JSON.parse
end

function savepage(fn::String, page::Dict)::Nothing
    open(fn, "w") do f
        JSON.print(f, page, 2)
    end
    nothing
end

function savepages(
        comp::String,
        years::AbstractVector{Int},
        divisions::AbstractVector{Int}=[1,2],
        query::Dict=Dict();
        maxpage=Inf
    )::Nothing
    
    @threads for year ∈ years
        println("starting $comp $year")
        for division ∈ divisions
            query["division"] = division
            page = 1
            done = false
            while !done & (page <= maxpage)
                query["page"] = page
                data = getpage(comp, year, query)
                if haskey(data, "leaderboardRows") && (length(data["leaderboardRows"]) > 0)
                    fn = joinpath(rawdir, "$(comp)_$(year)_$(division)_$(page).json")
                    savepage(fn, data)
                else
                    done = true
                end
                page += 1
            end
        end
        println("finished $comp $year")
    end
    nothing
end

function savepages(
        comp::String,
        year::Int,
        division::Int,
        query::Dict=Dict();
        maxpage=Inf
    )::Nothing
    
    savepages(comp, [year], [division], query, maxpage=maxpage)
end

##

if isdir(rawdir)
    rm(rawdir, recursive=true)
end
mkpath(rawdir)

savepages(
    "games",
    2007:2022,
    [1:10; 12:17] #skip the teams division (number 11)
)

savepages(
    "open",
    2011:2022,
    [1:10; 12:17], #skip the teams division (number 11)
    maxpage=50
)

##