
function getCurUrlParams() {
    var cur_url = "" + document.URL;
    var url_parts = cur_url.split("?");
    
    var params = {};
    if (url_parts.length > 1) {
        var param_parts = url_parts[1].split("&");
        for(var i =0 ; i< param_parts.length; i++) {
            var p = param_parts[i].split("=");
            params[p[0]] = p[1];
        }
    }
    
    return params;
}

function get_max_trend(cluster) {
    var trend_vals = []
    for(var i=0; i<cluster["members"].length; i++) {
        trend_vals.push(parseFloat(cluster["members"][i]["trend"]));    
    }
    trend_vals.sort().reverse();

    return trend_vals[0];
}

function set_trend_color(cluster) {
    var avg_trend = 0;
    for(var i=0; i<cluster["members"].length; i++) {
        avg_trend += parseFloat(cluster["members"][i]["trend"]);
    }
    avg_trend = avg_trend / cluster["members"].length;

    var trend_class = "trend-unknown";
    var sign = "";
    if (avg_trend >0) {
        trend_class = "trend-raise";
        sign = "+";
    } else if (avg_trend < 0) {
        trend_class = "trend-fall";
    }
    
    cluster["avg_trend"] = sign +  avg_trend.toFixed(2);
    cluster["trend_class"] = trend_class;
}

function goBack() {
    var skip;
    skip = parseInt(getCurUrlParams()["skip"]);
    if (isNaN(skip)) {
        skip = 0;
    }
    window.location.assign("/?skip=" + parseInt(skip + 1))
}

function loadClusters(parse_url_args) {
    var skip = parseInt(getCurUrlParams()["skip"]);
    
    if (isNaN(skip)) {
        skip = 0;
    }
    
    console.log("loadClusters");
    $.get( "/api/cluster?skip=" + skip, function( data ) {
        try{
        var resp = JSON.parse(data);
    
        var cl = resp["clusters"];

        cl.sort(function(a,b) {
            var a_val = get_max_trend(a);
            var b_val = get_max_trend(b);

            if (a_val < b_val) return -1;
            if (a_val > b_val) return 1;
            return 0;
        }).reverse();

        var limit = 30;

        var cl2= [];
        for(var i=0; i<cl.length; i++) {
            var mems = $.map(cl[i]["members"], function(l) {
                return l["text"];
            })

            try {
                set_trend_color(cl[i]);
            } catch(e) {
                console.log(e);
            }

            cl[i]["query_string"] = mems.join("+"); 
            if ( cl[i]["members_len"] > 1) {
                cl2.push(cl[i]);
            }
        }
        cl = cl2.slice(0, 20);


        var groups = [];
        var per_group = 1;
        while(cl.length > 0) {
            if (cl.length < per_group) {
                groups.push(cl);
                break;
            }
            groups.push(cl.slice(0, per_group));
            cl = cl.slice(per_group);
        }

        var source = $("#cluster-template").html();
        var template = Handlebars.compile(source);

        $( "#cluster-holder" ).html( template({"groups": groups, "update_time": resp["update_time"]}) );
        } catch (e){
            console.log(e);
        }
    });
}

