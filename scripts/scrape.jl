using DrWatson
@quickactivate "XFT"
using ProgressMeter
using URIs, HTTP, JSON

## ----------------------------------------------------------------------------

const rawdir = datadir("raw", "competition-results")

## ----------------------------------------------------------------------------

function cleardir(dir::String)::Nothing
    isdir(dir) && rm(dir, recursive=true)
    mkpath(dir)
    nothing
end

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
    divisions::AbstractVector{Int}=[1, 2],
    query::Dict=Dict();
    maxpage=Inf,
    sleepavg=0.01,
    sleepfloor=0.01
)::Nothing

    for year ∈ years
        #target directory
        dir = joinpath(rawdir, comp, year |> string)
        #clear the directory if it exists
        cleardir(dir)
        #download and save all the controls
        savejson(
            joinpath(dir, "$(comp)_$(year)_controls.json"),
            getcontrols(comp, year)
        )
        #download and save all leaderboard information
        for division ∈ divisions
            println("looking for $year $comp division $division results")
            subdir = joinpath(dir, "division-$division")
            query["division"] = division
            page = 1
            done = false
            prog = ProgressUnknown("pages downloaded:")
            while !done & (page <= maxpage)
                query["page"] = page
                sleep(max(sleepavg*rand(), sleepfloor)) #seems to prevent rate-limiting but results vary
                data = getpage(comp, year, query)
                if haskey(data, "leaderboardRows") && (length(data["leaderboardRows"]) > 0)
                    fn = joinpath(subdir, "$(comp)_$(year)_division_$(division)_page_$(page).json")
                    !isdir(subdir) && mkdir(subdir)
                    savejson(fn, data)
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

divisions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 18, 19, 36, 37, 38, 39]

##

saveboards("games", 2007:2023, divisions)

##

saveboards("open", 2011:2024, divisions, maxpage=10_000)

##
