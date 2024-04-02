using DrWatson
@quickactivate "XFT"

##

const rawdir = datadir("raw")

##

function countfiles(directory::String, extension::String)::Nothing
    L = splitpath(directory) |> length
    for (root, _, fns) ∈ walkdir(directory)
        level = (splitpath(root) |> length) - L
        println(repeat("  ", level), root)
        n = count(fns) do fn
            _, ext = splitext(fn)

            ext == extension
        end
        if n > 0
            println(repeat("  ", level + 1), n)
        end
    end
    nothing
end

countfiles(joinpath(rawdir, "competition-results", "open"), ".json")

##
