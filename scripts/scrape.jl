using ProgressMeter
using URIs, HTTP, JSON

## ----------------------------------------------------------------------------

const rawdir = joinpath("..", "data", "raw")

## ----------------------------------------------------------------------------

getjson(uri::URI)::Dict = HTTP.get(uri).body |> String |> JSON.parse

function savejson(fn::String, json::Dict, indent::Int=2)::Nothing
    open(fn, "w") do f
        JSON.print(f, json, indent)
    end
    nothing
end

function controlsuri(comp::String, year::Int)::URI
    URI(
        scheme="https",
        host="games.crossfit.com",
        path="/competitions/api/v1/competitions/$(comp)/$(year)?expand[]=controls"
    )
end

function getcontrols(comp::String, year::Int)::Dict
    controlsuri(comp, year) |> getjson
end

function pageuri(comp::String, year::Int, query::Dict=Dict())::URI
    URI(
        scheme="https",
        host="c3po.crossfit.com",
        path="/api/competitions/v2/competitions/$(comp)/$(year)/leaderboards",
        query=query
    )
end

function getpage(comp::String, year::Int, query::Dict=Dict())::Dict
    pageuri(comp, year, query) |> getjson
end

function saveboards(
        comp::String,
        years::AbstractVector{Int},
        divisions::AbstractVector{Int}=[1,2],
        query::Dict=Dict();
        maxpage=Inf
    )::Nothing
    
    for year ∈ years
        println("starting $comp $year")
        #download and save all the controls
        savejson(
            joinpath(rawdir, "$(comp)_$(year)_controls.json"),
            getcontrols(
                comp,
                year
            )
        )
        #download and save all leaderboard information
        for division ∈ divisions
            println("starting division $division")
            query["division"] = division
            page = 1
            done = false
            prog = ProgressUnknown("pages downloaded:")
            while !done & (page <= maxpage)
                query["page"] = page
                sleep(rand() + 0.2) #seems to prevent rate-limiting
                data = getpage(comp, year, query)
                if haskey(data, "leaderboardRows") && (length(data["leaderboardRows"]) > 0)
                    savejson(
                        joinpath(
                            rawdir,
                            "$(comp)_$(year)_division_$(division)_page_$(page).json"
                        ),
                        data
                    )
                else
                    done = true
                end
                ProgressMeter.next!(prog)
                page += 1
            end
            ProgressMeter.finish!(prog)
        end
        println("finished $comp $year")
    end
    nothing
end

## ----------------------------------------------------------------------------

#this clears and remakes the raw data directory
if isdir(rawdir)
    rm(rawdir, recursive=true)
end
mkpath(rawdir)

##

saveboards(
    "games",
    2007:2023,
    [1,2] #[1:10; 12:39] #skip the teams division (number 11)
)

##

saveboards(
    "open",
    2011:2022,
    [1,2], #[1:10; 12:39], #skip the teams division (number 11)
    maxpage=100
)

##