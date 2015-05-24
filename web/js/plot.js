
function getCurUrlParamArrays() {
    var cur_url = "" + document.URL;
    var url_parts = cur_url.split("?");
    
    var params = {};
    if (url_parts.length > 1) {
        var param_parts = url_parts[1].split("&");
        for(var i =0 ; i< param_parts.length; i++) {
            var p = param_parts[i].split("=");
            var key = p[0];
            var val = p[1];
            if (!(key in params)) {
                params[key] = [];
            }
            params[key].push(p[1]);
        }
    }
    
    return params;
}


function linear_approx(series, seriesLabel) {
    var xs = [];
    var ys = []
    for(var i =0; i<series.length; i++) {
        xs.push(series[i][0]);
        ys.push(series[i][1]);
    }

    var y2s = linear_approx_full(ys, xs);

    var data = [];
    for (var i = 0; i<series.length; i++) {
        data.push([xs[i], y2s[i]]);
    }

    return {"data": data, "label": '"' + seriesLabel + '" (аппроксимация)' 
    }
}
function linear_approx_full(series, xs) {
    var n = series.length;
    var xy_mean = 0;
    var x_mean = 0;
    var y_mean = 0;
    var x2_mean = 0;
    for(var i =0; i<n; i++) {
        xy_mean += xs[i]*series[i];
        y_mean += series[i];
        x_mean += xs[i];
        x2_mean += xs[i] * xs[i];
    }
    xy_mean = xy_mean / n;
    x_mean = x_mean / n;
    y_mean = y_mean /n;
    x2_mean = x2_mean /n;

    var b = (xy_mean - x_mean * y_mean) / (x2_mean - x_mean * x_mean);
    var a = y_mean - b * x_mean ;

    console.log("A: " + a + "; B: " + b + "; x_mean: " + x_mean + "; y_mean: " + y_mean);   
 
    var approx = []
    for(var i =0; i<n; i++) {
        approx.push(a + b * i);
    }

    return approx;
}

function changeGraph() {
    var word = $("#wordSelector").val();
    if (word != undefined) {
        window.location.assign('/graph2?word=' + encodeURIComponent(word));
    }
}

function getTimeLabel(time_hour) {
    var month = time_hour.substr(4,2);
    var day   = time_hour.substr(6,2);
    var hour  = time_hour.substr(8,2);

    var label = month +"." + day + " " + hour + ":00";

    return label;
}

function addWordAndPlot(wordToPlot, color, plotDataSeries, showApprox, labelsLong) {
    wordToPlot = decodeURIComponent(wordToPlot).trim();

    var encodedWord = encodeURIComponent(wordToPlot.toLowerCase().replace('#',''));

    var query = "/api/trend?word=" + encodedWord;
    if ($("#timeSelector1").val() != "") {
        query += "&time1=2015" + $("#timeSelector1").val();
    }
    if ($("#timeSelector2").val() != "") {
        query += "&time2=2015" + $("#timeSelector2").val();
    }

    $.get(query, function( data ) {
        try{
            var resp = JSON.parse(data);
            var dataSeries = resp["dataSeries"];
            var labels = [];
            var data = [];
            var tickDist = Math.round(dataSeries.length / 5);
            for(var i=0; i<dataSeries.length; i++) {
                var label = getTimeLabel(dataSeries[i]["hour"]);
                var unixtime = parseFloat(dataSeries[i]["utc_unixtime"]);

                if (i % tickDist == 0) {
                    labels.push([unixtime, label]); 
                }
                labelsLong[unixtime] = label;
                data.push([unixtime, dataSeries[i]["count"]]); 
            } 
            plotDataSeries.push({"label": wordToPlot, "data": data, "color": color,
                //lines: {
                //    show: true,
                //    fill: true,
                //    fillColor: { colors: [{ opacity: 0.3 }, { opacity: 0.1}] }
                //}
                bars: {
                    show: true,
                    barWidth: 3600, //hour
                    fill: true,
                    fillColor: { colors: [ { opacity: 0.5 }, { opacity: 0.1 } ] }
                }
            });
            if (showApprox) {
                plotDataSeries.push(linear_approx(data, wordToPlot));
            }
            $.plot("#wordsChart", plotDataSeries, {
                yaxis: {
                    min: 0
                },
                xaxis: {
                    ticks: labels 
                },
                grid: {
                    hoverable: true,
                    borderWidth: 0
                }
            });
            

            $("#wordsChart").bind("plothover", function (event, pos, item) {

                if (item) {
                    var x = item.datapoint[0],
                        y = item.datapoint[1];

                    var pointLabel = item.series.label;

                    var times = "раз";
                    var lastDigit = String(y).substr(-1, 1);
                    if ( lastDigit == "2" || lastDigit == "3" || lastDigit == "4") {
                        times = "раза";
                    }

                    $("#tooltip").html('"' + pointLabel + '"' + " " + labelsLong[x] + "<br/> " + y + " " + times)
                        .css({top: item.pageY+5, left: item.pageX+5})
                        .fadeIn(200);
                } else {
                    $("#tooltip").hide();
                }
            });            
        } catch (e){
            console.log(e);
        }
    })
    .fail(function() {
            console.log("Unknown error");
    });

}

function loadGraph() {

    $('#wordSelector').bind('keypress',function (event){
      if (event.keyCode === 13){
        $("#change-graph-btn").trigger('click');
      }
    });

    // Get context with jQuery - using jQuery's .get() method.

    var bigWordToPlot = getCurUrlParams()["word"];
    if (bigWordToPlot == undefined) {
        return;
    }
    bigWordToPlot = decodeURIComponent(bigWordToPlot).trim();
    $("#wordSelector").val(bigWordToPlot);
    console.log(bigWordToPlot);

    var showTrend = "trend" in getCurUrlParams();
    
    var wordsToPlot = bigWordToPlot.split(' ');
    var plotDataSeries = [];
    var labelsLong = {};

    for(var k=0; k<wordsToPlot.length && k < 5; k++) {
        if (wordsToPlot[k] == "") {
            continue;
        }
        addWordAndPlot(wordsToPlot[k], k, plotDataSeries, showTrend, labelsLong); 
    }

}


