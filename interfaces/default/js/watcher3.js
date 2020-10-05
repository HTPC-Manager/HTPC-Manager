$.ajaxSetup({
    timeout: 6000000
});
var profiles = $("<select id=\"profiles\">");
var cpcat = "";
var themoviedb_url = "//api.themoviedb.org/3/movie/{id}?api_key=2931bba1620c3c14c612ab820b828365";
$(document).ready(function(){
    $("#searchform").submit(function(e){
        e.preventDefault();
        var search = $("#moviename").val();
        if(search){
            searchMovie(search);
        }
    });

    // Load data on tab display
    $("a[data-toggle=\"tab\"]").click(function(e){
        $(".search").val("");
    }).on("shown", reloadTab);
    $(window).trigger("hashchange");


    // Disable nzbsearch
    $("#menu-search").submit(function(e){
        e.preventDefault();
        reloadTab($(e.target).find(".search").val());
    });


    $(".search").keyup(function(event){
        if(event.keyCode === 27){
            $(".search").val("");
            reloadTab("");
        }
    });


    $.get(WEBDIR + "watcher3/GetProfiles", function(data){
        if(data === null) return;
        $.each(data.list, function(i, item){
            profiles.append($("<option>").val(item).text(item));
        });
        if(data.default) profiles.val(data.default);
    });

    $.get(WEBDIR + "watcher3/GetCategories", function(data){
        if(data.length <= 0) return;
        cpcat = $("<select id=\"category_id\">");
        $.each(data, function(i, item){
            cpcat.append($("<option>").val(item).text(item));
        });
    });

    $("#postprocess").click(function(e){
        e.preventDefault();
        Postprocess();
    });

    $("#cp_update").click(function(e){
        e.preventDefault();
        update();
    });

});

function showMovies(pResult, pHTMLElement){
    pHTMLElement.empty();
    $(".spinner").hide();

    if(pResult === null || pResult.total === 0){
        pHTMLElement.append($("<li>").html("No " + strStatus + " movies found"));
        return;
    }

    $.each(pResult.movies, function(nIndex, pMovie){
        var strHTML = $("<a>").attr("href", "#").click(function(pEvent){
            pEvent.preventDefault();
            showMovie(pMovie);
        });
        var src = "holder.js/100x150/text:No artwork";
        if(pMovie.poster && pMovie.imdbid){
            src = WEBDIR + "watcher3/GetImage?w=100&h=150&imdbid=" + pMovie.imdbid;
        } else if(pMovie.poster_url){
            src = WEBDIR + "watcher3/GetImage?w=100&h=150&url=" + pMovie.poster_url;
        }
        strHTML.append($("<img>").attr("src", src).attr("width", "100").attr("height", "150").addClass("thumbnail"));

        if(pMovie.status === 'Finished' || pMovie.status === 'Disabled'){
            strHTML.append($("<i>").attr("title", "Download").addClass("fa fa-arrow-circle-o-down fa-inverse status"));
        }

        strHTML.append($("<h6>").addClass("movie-title").html(shortenText(pMovie.title, 16)));
        pHTMLElement.append($("<li>").attr("id", pMovie.imdbid).append(strHTML));
    });
    Holder.run();
}


function getMovies(strStatus, pHTMLElement, options){
    /*
    if (options.f.length) {
        // remove all old content if it was a search
        pHTMLElement.empty();
    }
    */
    var o = options || {};
    o.status = strStatus;
    pHTMLElement.empty();
    $(".spinner").show();

    $.getJSON(WEBDIR + "watcher3/GetMovieList/", o, function(pResult){
        showMovies(pResult, pHTMLElement);
    });

}


function reloadTab(searchString){
    var options = {};
    if(typeof searchString == "string") options.f = searchString;

    if($("#library").is(":visible")){
        $(".search").attr("placeholder", "Filter library");
        getMovies("done", $("#library-grid"), options);
    } else if($("#wanted").is(":visible")){
        $(".search").attr("placeholder", "Filter wanted");
        getMovies("active", $("#wanted-grid"), options);
    } else if($("#dashboardsoon").is(":visible")){
        getMovies("soon", $("#dashboardsoon-grid"));
    } else if($(".themoviedb-category").is(":visible")){
        var category = $(".themoviedb-category:visible").attr("id");
        getCharts(category);
    }

}

function getMovieLists(){
    getMovies("done", $("#library-grid"));
    getMovies("active", $("#wanted-grid"));
}

function addMovie(movieid, profile, title, cat){
    var data = {
        movieid: movieid,
        profile: encodeURIComponent(profile),
        category: encodeURIComponent(cat),
        title: encodeURIComponent(title)
    };
    $.getJSON(WEBDIR + "watcher3/AddMovie", data, function(result){
        if(result && result.response){
            notify("Watcher", "Added " + title, "success");
            $("a[href=#wanted]").tab("show")
        } else {
            notify("Watcher", "Failed to add " + title + "\n" + (result && result.error || ""), "error");
        }
    });
}

function editMovie(id, key, value){
    params = {imdbid: id};
    params[key] = encodeURIComponent(value);
    $.getJSON(WEBDIR + "watcher3/EditMovie", params, function(result){
        if(result.response){
            notify("Watcher", key + " changed", "success");
        } else {
            notify("Watcher", "An error occured.", "error");
        }
    });
}

function deleteMovie(id, name, delete_file){
    $.getJSON(WEBDIR + "watcher3/DeleteMovie", {
        imdbid: id,
        delete_file: !!delete_file
    }, function(result){
        if(result.response){
            $("#" + id).fadeOut();
            getMovieLists();
        } else {
            notify("Watcher", "An error occured:\n" + (result.error || ""), "error");
        }
    });
}

function refreshMovie(id, name, tmdbid){
    $.getJSON(WEBDIR + "watcher3/RefreshMovie", {
        imdbid: id,
        tmdbid: tmdbid || null
    }, function(result){
        if(result.response){
            notify("Watcher", name + "\n" + result.message, "info");
        } else {
            notify("Watcher", result.error || "An error occured.", "error");
        }
    });
}

function showSearchResults(movies, grid){
    grid.empty();
    $.each(movies, function(i, movie){
        var finished = movie.status === 'Finished' || movie.status === 'Disabled';
        var link = $(finished ? "<span>" : "<a>");
        if(!finished){
            link.attr("href", "#").click(function(e){
                e.preventDefault();
                showMovie(movie, cpcat);
            });
        }
        var src = "holder.js/100x150/text:No artwork";
        if(movie.poster_url){
            src = WEBDIR + "watcher3/GetImage?w=100&h=150&url=" + movie.poster_url;
        }
        link.append($("<img>").attr("src", src).addClass("thumbnail"));
        if(finished){
            link.append($("<i>").attr("title", "Download").addClass("fa fa-arrow-circle-o-down fa-inverse status"));
        }
        var title = shortenText(movie.title, 16);
        link.append($("<h6>").addClass("movie-title").html(title));
        grid.append($("<li>").attr("id", movie.tmdbid).append(link));
    });
}

function searchMovie(q){
    var grid = $("#result-grid").empty();
    $("a[href=#result]").tab("show");
    $(".spinner").show();
    $.getJSON(WEBDIR + "watcher3/SearchMovie", {
        q: encodeURIComponent(q)
    }, function(result){
        $(".spinner").hide();
        if(result.response){
            showSearchResults(result.results, grid)
        } else {
            grid.append($("<li>").html(result.error));
        }
        Holder.run();
    })
}

function showMovie(movie, was_search, info){
    var plot = movie.plot;
    var year = movie.year;
    var modalButtons;

    if(typeof info == "undefined" && movie.tmdbid){
        $.get(themoviedb_url.replace("{id}", movie.tmdbid))
        .done(function(data){
            showMovie(movie, was_search, data);
        })
        .fail(function(){
            showMovie(movie, was_search, null);
        });
        return;
    }

    var src = "holder.js/154x231/text:No artwork";
    if(movie.poster && movie.imdbid){
        src = WEBDIR + "watcher3/GetImage?w=100&h=150&imdbid=" + movie.imdbid;
    } else if(movie.poster_url){
        src = WEBDIR + "watcher3/GetImage?w=100&h=150&url=" + movie.poster_url;
    }
    var modalImg = $("<img>").attr("src", src).addClass("thumbnail pull-left");

    var modalInfo = $("<div>").addClass("modal-movieinfo");
    if(info && info.runtime){
        modalInfo.append($("<p>").html("<b>Runtime:</b> " + parseSec(info.runtime)));
    }
    modalInfo.append($("<p>").html("<b>Plot:</b> " + plot));
    if(info){
        if(info.directors){
            modalInfo.append($("<p>").html("<b>Director:</b> " + info.directors));
        }
        if(info.genres){
            modalInfo.append($("<p>").html("<b>Genre:</b> " + info.genres.map(function(i){
                return i.name;
            }).join(", ")));
        }
    }

    if(movie.score){
        modalInfo.append(
            $("<div>").raty({
                readOnly: true,
                path: null,
                score: (movie.score / 2)
            })
        );
    }

    var titles = $("<select>").attr("id", "titles");
    if(was_search){
        $.each([movie.title], function(i, item){
            titles.append($("<option>").text(item).val(item).prop("selected", item.default));
        });
    } else {
        var title_list = [movie.title];
        if(movie.alternative_titles)
            title_list = title_list.concat(movie.alternative_titles.split(','));
        $.each(title_list, function(i, item){
            titles.append($("<option>").text(item).val(item));
        });
    }

    profiles.unbind();
    var title = movie.title;
    if(year) title += " (" + year + ")";
    profiles.change(function(){
        editMovie(movie.imdbid, 'profile', profiles.val());
    }).val(movie.profile_id);
    titles.change(function(){
        editMovie(movie.imdbid, 'title', titles.val());
    });
    // TODO add option to change language and category

    // If showmovie is called from a search
    if(was_search){
        // Was called from search
        modalButtons = {
            "Add": function(){
                var category;
                if(!was_search.length){
                    category = "Default";
                } else {
                    category = was_search.val();
                }
                addMovie(movie.tmdbid, profiles.val(), titles.val(), category);
                hideModal();
            }
        };
    } else {
        modalButtons = {
            "Delete": function(){
                if(confirm("Do you want to delete: " + title + "?")){
                    var delete_file = false;
                    if(movie.finished_file && confirm("Do you want to delete file: " + movie.finished_file + "?")){
                        delete_file = true;
                    }
                    deleteMovie(movie.imdbid, title, delete_file);
                    hideModal();
                }
            },
            "Refresh": function(){
                refreshMovie(movie.imdbid, title, movie.tmdbid);
                hideModal();
            }
        };
    }
    if(movie.imdbid){
        $.extend(modalButtons, {
            "IMDb": function(){
                window.open("http://www.imdb.com/title/" + movie.imdbid, "IMDb")
            }
        });
    }
    if(movie.tmdbid){
        $.extend(modalButtons, {
            "TheMovieDB": function(){
                window.open("https://www.themoviedb.org/movie//" + movie.tmdbid, "TheMovieDB")
            }
        });
    }

    modalInfo.append(titles, profiles);

    // Adds the category if showmovie was run from search
    if(was_search){
        modalInfo.append(cpcat);
    }

    if(info && info.backdrop_path){
        var url = "https://image.tmdb.org/t/p/original" + info.backdrop_path;
        var backdrop = WEBDIR + "watcher3/GetImage?w=675&h=400&o=10&url=" + encodeURIComponent(url);
        $(".modal-fanart").css({
            "background-image": "url(" + backdrop + ")"
        });
    }

    $.getJSON(WEBDIR + "watcher3/GetReleases", {id: movie.imdbid})
        .done(function(data){
            if (data.response){
                var strTable = MovieReleases(data.results);
                $.extend(modalButtons, {
                    "Releases": function(){
                        $(".modal-body").html(strTable);
                    }
                });
            }
        })
        .complete(function(){
            var modalBody = $("<div>").append(modalImg, modalInfo);
            showModal(title, modalBody, modalButtons);
            // since ff and ie sucks balls
            $("#profiles option")[0].selected = true;
            Holder.run();
        });
}

function MovieReleases(releases) {
    var strTable = $("<table>").addClass("table table-striped table-hover").append(
        $("<tr>").append("<th>Action</th>").append("<th>Name</th>").append("<th>Indexer</th>").append("<th>Leechers/Seeders</th>").append("<th>Score</th>").append("<th>Size</th>")
    );

    //Loop all with movies with releases. Dont add button if its done or downloading.
    $.each(releases, function(nIndex, pRelease){
        //Don't display release if watcher3 rejected it
        if (pRelease.reject_reason) return;
        var action = $("<td>");
        if (pRelease.status == "Available" || pRelease.status == "Bad") {
	    action.append(
	        $("<a>").attr("href", "#").append(
                    $("<i>").attr("title", "Download").addClass("fa fa-download")
                ).click(function(pEvent){
                    pEvent.preventDefault();
                    hideModal();
                    $.getJSON("DownloadRelease", {id: pRelease.guid, kind: pRelease.type});
                })
	    );
            if (pRelease.status == "Bad")
                action.append($("<i>").attr("title", "Bad").addClass("fa fa-ban"));
	} else {
            action.append($("<i>").attr("title", pRelease.status).addClass("fa fa-" + (pRelease.status == "Snatched" ? "arrow-circle-down" : "check-circle")));
	}
        strTable.append(
            $("<tr>").append(
                action,
                $("<td>").append(
                    $("<a>").attr("href", "#").text(pRelease.title).click(function(pEvent){
                        pEvent.preventDefault();
                        window.open(pRelease.info_link);
                    })
                ),
                $("<td>").append(pRelease.indexer),
                $("<td>").append(pRelease.leechers + '/' + pRelease.seeders),
                $("<td>").append(pRelease.score),
                $("<td>").html(bytesToSize(pRelease.size))
            )
        );
    });

    return strTable;
}

function Postprocess(){
    $.get(WEBDIR + "watcher3/Postprocess", function(r){
        state = (r && r.response) ? "success" : "error";
        notify("Watcher", "Postprocess", state);
    });
}

function update(){
    $.get(WEBDIR + "watcher3/Update", function(data){
        if(!data || data.status === "error"){
            notify("Watcher", data && data.error ? data.error : "is not updating", "error")
        } else if(data.status === "current"){
            notify("Watcher", "is updated", "success")
        } else if(data.updated){
            notify("Watcher", "is updating", "success")
        } else if(data.status === "behind"){
            notify("Watcher", "is " + data.behind_count + " commit" + (data.behind_count === 1 ? "" : "s") + " behind", "info")
        } else {
            notify("Watcher", "update response unrecognized", "error")
        }
    })
}

function getCharts(cat){
    var spinner = $(".spinner").show();

    $.getJSON(themoviedb_url.replace("{id}", cat), function(data){
        if(data === null || data.results.length === 0){
            return;
        }
        var movies = data.results.map(function(movie){
            return {
                tmdbid: movie.id,
                plot: movie.overview,
                title: movie.title,
                score: movie.vote_average,
                poster_url: "https://image.tmdb.org/t/p/original" + movie.poster_path
            }
        });
        $(".spinner").hide();
        showSearchResults(movies, $("#" + cat + "-grid"));
    });
}
