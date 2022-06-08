function ChartSlider($document) {

    // Helper function to find element inside a parent.
    var findElement = function(parent, handle) {
        return $(parent).find('.handle.' + handle)
    }
    // Move slider element.
    var moveHandle = function(elem, posX) {
        $(elem).css("left", posX + '%')
    };
    // Move range line.
    var moveRange = function(elem, posMin, posMax) {
        $(elem).find('.range').css("left", posMin + '%')
        $(elem).find('.range').css("width", posMax - posMin + '%')
    };
    // Get date from percentage based on min/max date.
    var getDateSeconds = function(minDate, maxDate, percentage) {
        return minDate + Math.round((maxDate - minDate) * (percentage / 100))
    };

    return {
        template: '<div class="slider horizontal">' +
            '<div class="range" ng-mousedown="mouseDown($event)"></div>' +
            '<i class="handle min btn btn-xs btn-default fa fa-caret-right" ' +
            'aria-hidden="true" ng-mousedown="mouseDown($event)" ' +
            'data-toggle="tooltip" data-placement="bottom" title=""></i>' +
            '<i class="handle max btn btn-xs btn-default fa fa-caret-left" ' +
            'data-toggle="tooltip" data-placement="bottom" title="" ' +
            'aria-hidden="true" ng-mousedown="mouseDown($event)"></i>' +
            '</div>',
        replace: true,
        restrict: 'E',
        scope: {
            valueMin: "=",
            valueMax: "=",
            metrics: "=",
            metricIndex: "@",
            ranges: "=",
            updateUrl: "&",
            filterByDate: "&",
            getEnvironmentIds: "&",
            formatDate: "&",
        },
        link: function postLink(scope, element, attrs) {
            // Initilization
            var target = null
            var dateMin, dateMax
            var dragging = false
            var startPointX = 0
            var xMin = scope.valueMin
            var xMax = scope.valueMax
            // Current metric.
            var currentMetric = scope.metrics[scope.metricIndex]
            moveHandle(findElement(element, "min"), xMin)
            moveHandle(findElement(element, "max"), xMax)
            moveRange(element, xMin, xMax)

            var minSeconds = getDateSeconds(
                currentMetric.chart.minDate,
                currentMetric.chart.maxDate,
                xMin)
            element.find(".min").attr("title",
                                      scope.formatDate({x: minSeconds}))
            var maxSeconds = getDateSeconds(
                currentMetric.chart.minDate,
                currentMetric.chart.maxDate,
                xMax)
            element.find(".max").attr("title",
                                      scope.formatDate({x: maxSeconds}))

            // Action control.
            scope.mouseDown = function($event) {
                dragging = true
                target = $event.target
                startPointX = $event.pageX

                $document.on('mousemove', function($event) {
                    if(!dragging) {
                        return
                    }

                    // Calculate handle position.
                    var moveDelta = $event.pageX - startPointX
                    var xCurrent = 0

                    if ($(target).hasClass('min')) {
                        xMin += moveDelta / element.outerWidth() * 100
                        if (xMin < 0) {
                            xMin = 0
                        } else if (xMin > xMax - 4) {
                            xMin = xMax - 4
                        } else {
                            // Prevent generating "lag" if moving outside.
                            startPointX = $event.pageX
                        }
                        xCurrent = xMin
                    } else if ($(target).hasClass('max')) {
                        xMax += moveDelta / element.outerWidth() * 100
                        if(xMax > 100) {
                            xMax = 100
                        } else if(xMax < xMin + 4) {
                            xMax = xMin + 4
                        } else {
                            startPointX = $event.pageX
                        }
                        xCurrent = xMax
                    } else {
                        xMin += moveDelta / element.outerWidth() * 100
                        xMax += moveDelta / element.outerWidth() * 100
                        if(xMax > 100) {
                            xMax = 100
                            xMin -= (moveDelta / element.outerWidth()) * 100
                        } else if (xMin < 0) {
                            xMin = 0
                            xMax -= (moveDelta / element.outerWidth()) * 100
                        } else {
                            startPointX = $event.pageX
                        }
                    }

                    // Move the Handle(s)
                    if ($(target).hasClass('range')) {
                        moveHandle(findElement(element, "min"), xMin)
                        moveHandle(findElement(element, "max"), xMax)
                    } else {
                        moveHandle(target, xCurrent)
                        // Move tooltip as well. Need small hack since we need
                        // it in the middle.
                        moveHandle($(target).parent().find('.tooltip'),
                                   xCurrent-4.5)
                    }
                    moveRange(element, xMin, xMax)

                    var minLimit = getDateSeconds(
                        currentMetric.chart.minDate,
                        currentMetric.chart.maxDate,
                        xMin)
                    var maxLimit = getDateSeconds(
                        currentMetric.chart.minDate,
                        currentMetric.chart.maxDate,
                        xMax)

                    scope.filterByDate({
                        chartPanel: currentMetric.chart,
                        minLimit: minLimit,
                        maxLimit: maxLimit
                    })

                    currentMetric.chart.updateAnnotations(
                        scope.getEnvironmentIds(),
                        minLimit,
                        maxLimit
                    )
                    currentMetric.chart.scatterChart.update()

                    // Update range.
                    scope.ranges[currentMetric.name][0] = Math.round(xMin)
                    scope.ranges[currentMetric.name][1] = Math.round(xMax)

                    // Finally, update handles' tooltips.
                    if ($(target).hasClass('min')) {
                        $(target).attr(
                            "title",
                            scope.formatDate({x: minLimit})).tooltip('fixTitle').tooltip('show')
                    } else if ($(target).hasClass('max')) {
                        $(target).attr(
                            "title",
                            scope.formatDate({x: maxLimit})).tooltip('fixTitle').tooltip('show')
                    } else {
                        $(target).parent().find(".min").attr(
                            "data-original-title",
                            scope.formatDate({x: minLimit}))
                        $(target).parent().find(".max").attr(
                            "data-original-title",
                            scope.formatDate({x: maxLimit}))
                    }
                });

                $document.mouseup(function() {
                    scope.updateUrl()
                    scope.$apply()
                    // Clean up tooltips if client moved away the pointer.
                    element.find('.handle:not(:hover)').tooltip('hide')
                    dragging = false
                    $document.unbind('mousemove')
                });
            };
        }
    };
}

function getYAxis(min, max) {
    var min = (min > 0) ? 0 : Math.round(1.2 * min)
    var max = Math.round(1.2 * max)
    return { min: min, max: max}
}

function ChartPanel($http, DATA) {

    var chartPanel = function(metric, data, environmentIds) {
        this.metric = metric
        this.data = data

        this.draw = function(target, environments, range) {
            var metric = this.metric
            var data = this.data

            var selected_environments = _.filter(environments, function(env) {
                return env.selected
            })

            var minCoefficient = chartPanel.slider.defaultResultsLimit
            var maxCoefficient = 1
            if (typeof range !== 'undefined' && range.length > 0) {
                minCoefficient = range[0] / 100
                maxCoefficient = range[1] / 100
            }

            var minLimit = this.minDate +
                Math.round((this.maxDate - this.minDate) * minCoefficient)
            var maxLimit = this.minDate +
                Math.round((this.maxDate - this.minDate) * maxCoefficient)

            // Filter out outliers from data[env.name] first here and manage them
            // separately.
            data[chartPanel.OUTLIER_LABEL] = []
            _.each(selected_environments, function(env) {
                data[env.name] = _.filter(data[env.name], function(point) {
                    if (point.length < 6 || point[5] == 'False') {
                        return true
                    } else {
                        data[chartPanel.OUTLIER_LABEL].push(point)
                        return false
                    }
                })
            })

            var datasets = []
            var min = 0
            var max = 0
            _.each(selected_environments, function(env) {
                if (data[env.name].length == 0) {
                    return
                }
                var line = chartPanel.filterData(data[env.name], minLimit, maxLimit)
                var low = chartPanel.filterData(data[env.name], minLimit, maxLimit, 6)
                var high = chartPanel.filterData(data[env.name], minLimit, maxLimit, 7)

                var series = _.map(line, function(p) { return p.y })
                min = Math.min(min, _.min(series))
                max = Math.max(max, _.max(series))

                // lower end of the range
                if (! _.isEqual(low, line)) {
                    datasets.push({
                        label: ':low:' + env.name,
                        data: low,
                        backgroundColor: env.range_color,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        borderColor: '#ffffff00', // transparent
                        yidx: 6,
                        fill: '+1'
                    })
                }

                // main line
                datasets.push({
                    label: env.name,
                    fill: false,
                    borderWidth: 2,
                    pointRadius: 1,
                    backgroundColor: env.fill_color,
                    borderColor: env.line_color,
                    data: line
                })

                // higher end of the range
                if (! _.isEqual(high, line)) {
                    datasets.push({
                        label: ':high:' + env.name,
                        data: high,
                        backgroundColor: env.range_color,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        borderColor: '#ffffff00', // transparent
                        yidx: 7,
                        fill: '-1'
                    })
                }
            })

            // Add outliers to dataset.
            if (data[chartPanel.OUTLIER_LABEL].length) {
                // Shallow clone the static dict.
                var outlier_dataset = Object.assign(
                    {}, chartPanel.OUTLIER_DATASET_OPTIONS)
                outlier_dataset.data = chartPanel.filterData(
                    data[chartPanel.OUTLIER_LABEL],
                    minLimit, maxLimit)
                datasets.push(outlier_dataset)
            }

            var ctx = document.createElement('canvas')
            ctx.setAttribute('id', this.metric.name)
            target.appendChild(ctx)

            var scatterChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: datasets
                },
                options: {
                    title: {
                        display: false,
                        text: metric.label
                    },
                    tooltips: {
                        callbacks: {
                            title: function(t, data_objects) {
                                var tooltip = t[0]
                                var dataset = data_objects.datasets[tooltip.datasetIndex]
                                var data_point = dataset.data[tooltip.index]
                                return chartPanel.formatDate(data_point.x)
                            },
                            beforeBody: function(t, data_objects) {
                                var tooltip = t[0]
                                var dataset = data_objects.datasets[tooltip.datasetIndex]
                                var data_point = dataset.data[tooltip.index]
                                var build_id = dataset.data[tooltip.index]
                                return "Build #" + data_point.build_id
                            }
                        },
                        intersect: false,
                        mode: 'index'
                    },
                    animation: {
                        duration: 0,
                    },
                    scales: {
                        yAxes: [{
                            ticks: getYAxis(min, max)
                        }],
                        xAxes: [{
                            type: 'linear',
                            position: 'bottom',
                            ticks: {
                                callback: chartPanel.formatDate
                            }
                        }]
                    },
                    annotation: {
                        drawTime: "afterDatasetsDraw",
                        annotations: [],
                    },
                    legend: {
                        labels: {
                            filter: function(item, chart) {
                                return (! item.text.match(/^:(low|high):/))
                            }
                        }
                    }
                }
            });
            this.scatterChart = scatterChart

            var env_ids = _.map(selected_environments, function(env) {
                return env.name
            })
            this.updateAnnotations(env_ids, minLimit, maxLimit)

            var user = ''
            if(window.user !== 'undefined') {
                user = window.user;
            }

            ctx.onclick = function(evt) {
                var point = scatterChart.getElementAtEvent(evt)[0]
                if (point === undefined || point === null) {
                    return
                }

                var data_point = datasets[point._datasetIndex].data[point._index]
                data_point._index = point._index

                var project_location = '/' + DATA.project
                var build_location = project_location + '/build/' + data_point.build_id + '/'
                if (metric.name == ":tests:" || user == 'AnonymousUser') {
                    window.open(build_location, '_blank')
                    return
                }

                $("#point_menu").show()
                document.getElementById('metric-' + metric.name)
                        .appendChild(document.getElementById("point_menu"))
                $("#point_menu").offset({
                    top: evt.clientY + $(window).scrollTop() - 10,
                    left: evt.clientX - 10
                })

                $("#point_menu > ul > li:first-child > a").attr("href", build_location)
                $("#point_menu > ul > li:nth-child(2) > a").unbind("click").bind("click", function() {
                    var url = project_location + '/toggle-outlier-metric/' + data_point.metric_id;
                    $http.post(url).then(function (result) {
                        var data = result.data
                        var is_outlier = datasets[point._datasetIndex].label === chartPanel.OUTLIER_LABEL;
                        chartPanel.moveOutlierDatapoint(datasets, data_point, data.environment, is_outlier);
                        scatterChart.update()
                        $("#point_menu").hide()
                    });
                });
            }
        }

        this.updateMinDate = function(environmentIds) {
            // This assumes that the metrics data is sorted by date.
            var minDate = Math.round(new Date() / 1000)
            var data = this.data
            _.each(environmentIds, function(name) {
                if (typeof data[name] !== "undefined" && data[name].length > 0) {
                    if (data[name][0][0] < minDate) {
                        minDate = data[name][0][0]
                    }
                }
            })
            this.minDate = minDate
        }

        this.updateMaxDate = function(environmentIds) {
            // This assumes that the metrics data is sorted by date.
            var maxDate = 0
            var data = this.data
            _.each(environmentIds, function(name) {
                if (typeof data[name] !== "undefined" && data[name].length > 0) {
                    if (data[name][data[name].length-1][0] > maxDate) {
                        maxDate = data[name][data[name].length-1][0]
                    }
                }
            })
            this.maxDate = maxDate
        }

        this.getThresholdAnnotations = function() {
            var metric_name = this.metric
            var annotations = []
            _.each(DATA.thresholds, function(threshold) {
                if (threshold.name == metric_name) {
                    annotations.push({
                        type: "line",
                        mode: "horizontal",
                        scaleID: "y-axis-0",
                        value: threshold.value,
                        borderColor: 'rgba(0,0,0,0.3)',
                        borderWidth: 2,
                        label: {
                            backgroundColor: 'rgba(169,68,66,0.5)',
                            content: threshold.name + "  " + threshold.value,
                            enabled: true
                        },
                    })
                }
            })

            return annotations
        }

        this.updateAnnotations = function(environmentIds, minLimit,
                                                          maxLimit) {
            var data = this.data
            var annotations = {}
            var y_adjust = 0

            _.each(environmentIds, function(name) {
                _.each(data[name], function(elem) {
                    if (elem[3] != "") {
                        if (elem[0] < maxLimit && elem[0] > minLimit) {
                            annotations[elem[0]] = {
                                type: "line",
                                mode: "vertical",
                                scaleID: "x-axis-0",
                                value: elem[0],
                                borderColor: 'rgba(0,0,0,0.3)',
                                borderWidth: 2,
                                label: {
                                    backgroundColor: 'rgba(51,122,183,0.5)',
                                    content: elem[3],
                                    yAdjust: -150 + y_adjust,
                                    enabled: true
                                },
                            }
                            // Offset the labels so they don't overlap
                            y_adjust += 25
                            if (y_adjust > 200) { y_adjust = 0 }
                        }
                    }
                })
            })

            this.scatterChart.options.annotation.annotations = Object.values(
                annotations).concat(this.getThresholdAnnotations())
            this.scatterChart.update()
        }

        this.updateMinDate(environmentIds)
        this.updateMaxDate(environmentIds)
    }

    chartPanel.filterData = function(data, minLimit, maxLimit, yidx) {
        if (yidx == undefined) {
            yidx = 1
        }
        var current_data = _.filter(data, function(point) {
            return point[0] >= minLimit && point[0] <= maxLimit
        }).map(function(point){
            var data_point = {
                x: point[0],
                y: point[yidx],
                build_id: point[2]
            }
            if (point.length > 4) {
                data_point['metric_id'] = point[4]
            }
            return data_point
        })
        return current_data
    }

    chartPanel.formatDate = function(x) {
        // Javascript Date() takes milliseconds and x
        // is seconds, so multiply by 1000
        // Check if x 'defaults' to [-1, 1] range which means there are no
        // results, and in that case return an empty string.
        if (Number.isNaN(x) || (x <= 1 && x >= -1)) {
            return ""
        } else {
            return (new Date(x * 1000)).toISOString().slice(0,10)
        }
    }

    chartPanel.getDatasetByLabel = function(datasets, label) {
        return _.find(datasets, function(element) {
            return element.label == label
        })
    }

    chartPanel.slider = {
        defaultResultsLimit: 0.8,
        rangeMax: 100
    };
    chartPanel.OUTLIER_LABEL = "outliers"
    chartPanel.OUTLIER_DATASET_OPTIONS = {
        label: chartPanel.OUTLIER_LABEL,
        fill: false,
        borderWidth: 2,
        pointRadius: 1.5,
        backgroundColor: "#ff0000",
        borderColor: "#ff2222",
        showLine: false,
        data: []
    }

    chartPanel.putDatapoint = function(data, data_point) {
        // Finds the right place for the data_point in data, based
        // on the datetime value, via binary search.
        var left = 0
        var right = data.length - 1
        while (left <= right) {
            var mid = left + Math.round((right-left)/2)
            if (data_point.x < data[mid].x && data_point.x >= data[mid-1].x) {
                data.splice(mid, 0, data_point)
                return
            } else if (data_point.x < data[mid-1].x) {
                if (mid == left + 1) {  // Leftmost one.
                    data.splice(0, 0, data_point)
                } else {
                    right = mid - 1
                }
            } else {
                if (mid == right) {  // Rightmost one.
                    data.push(data_point)
                    return
                } else {
                    left = mid
                }
            }
        }
    }

    chartPanel.moveOutlierDatapoint = function(datasets, data_point,
                                               environment, is_outlier) {
        // Move a datapoint from/to one dataset to/from the 'outlier' dataset.
        // If the outlier dataset is not defined yet, set some default options
        // for it and add it to the chart datasets.
        var outlier_dataset = chartPanel.getDatasetByLabel(
            datasets, chartPanel.OUTLIER_LABEL)
        if (typeof outlier_dataset === 'undefined') {
            outlier_dataset = chartPanel.OUTLIER_DATASET_OPTIONS
            datasets.push(outlier_dataset)
        }
        var target_dataset = chartPanel.getDatasetByLabel(
            datasets, environment)
        if (!is_outlier) {
            target_dataset.data.splice(data_point._index, 1)
            outlier_dataset.data.push(data_point)
        } else {
            outlier_dataset.data.splice(data_point._index, 1)
            chartPanel.putDatapoint(target_dataset.data, data_point)
        }
    }

    return chartPanel
}

function ChartsController($scope, $http, $location, $compile, ChartPanel, DATA) {
    $scope.toggleEnvironments = function() {
        _.each($scope.environments, function(env) {
            env.selected = !env.selected
        })
        $scope.environmentsChanged()
    }

    $scope.getEnvironmentIds = function() {
        var selected = _.filter($scope.environments, function(env) {
            return env.selected
        })
        return _.map(selected, function(env) { return env.name })
    }

    $scope.environmentsChanged = function() {
        _.each($scope.selectedMetrics, function(m) {
            m.chart.updateMinDate($scope.getEnvironmentIds)
            m.chart.updateMaxDate($scope.getEnvironmentIds)
            m.drawn = false
        })
        $scope.update()
    }

    $scope.getMetricIds = function() {
        return _.map($scope.selectedMetrics, function(m) {
            return m.name
        })
    }

    $scope.addMetric = function(metric) {
        var existing = _.find($scope.selectedMetrics, function(m) {
            return m.name == metric.name
        })
        if (!existing) {
            $scope.selectedMetrics.push(metric)
        }
        $scope.metric = undefined
        $scope.ranges[metric.name] = Array()
        $scope.update()
    }

    $scope.removeMetric = function(metric) {
        _.remove($scope.selectedMetrics, function(m) {
            return m.name == metric.name
        })
        var chart_div = document.getElementById('metric-' + metric.name)
        chart_div.remove()
        metric.drawn = false
        delete $scope.ranges[metric.name]
        $scope.update()
    }

    $scope.download = function(callback) {
        var params = {
            metric: $scope.getMetricIds(),
            environment: $scope.getEnvironmentIds()
        }
        if (params.metric.length == 0 || params.environment.length == 0) {
            callback()
            return
        }

        var endpoint = '/api/data/' + $scope.project + '/'
        $http.get(endpoint, { params: params }).then(function(response) {
            $scope.data = response.data
            $scope.calculate_max_results()
            callback()
        })
    }

    $scope.redraw = function() {
        _.each($scope.selectedMetrics, function(metric, index) {
            if (! metric.drawn) {
                var data = $scope.data[metric.name]
                var chart = new ChartPanel(metric, data,
                                           $scope.getEnvironmentIds())

                var target_id = 'metric-' + metric.name
                var target = document.getElementById(target_id)
                if (target) {
                    target.innerHTML = ''
                } else {
                    var target = document.createElement('div')
                    target.id = target_id
                    target.classList.add('chart-container')
                    document.getElementById('charts').appendChild(target)
                }

                var title_container = "<div>" +
                    "<div class='h4 col-md-11 text-center'>" + metric.label +
                    "</div><div id='" + metric.name + "-div'"+"class='h4 pull-right'><span><button " +
                    "ng-click='toggleFullScreen(\"" + target_id +
                    "\")' class='btn btn-default btn-xs' " +
                    "title='Toggle Fullscreen'><i class='fa fa-expand' " +
                    "aria-hidden='true'></i></button></span></div></div>"
                var elem = $compile(title_container)($scope)
                $(target).append(elem)

                var min_value = ChartPanel.slider.defaultResultsLimit * 100;
                var max_value = ChartPanel.slider.rangeMax
                if (typeof $scope.ranges[metric.name] !== 'undefined' && $scope.ranges[metric.name].length > 0) {
                    min_value = $scope.ranges[metric.name][0]
                    max_value = $scope.ranges[metric.name][1]
                }

                chart.draw(target, $scope.environments,
                           $scope.ranges[metric.name])
                metric.chart = chart
                if (! metric.dynamic) {
                    metric.drawn = true
                }
                var canvas_id = document.getElementById(metric.name).id
                var button_id = canvas_id + "-anchor"
                var canvas_div = document.getElementById(metric.name+'-div').children[0]
                var download_elem = "<a id='"+ button_id + "' ng-click='downloadChartImage(\""+ canvas_id + "\""+
                    ",\"" + button_id + "\")' class='btn btn-default btn-xs'" +
                    "title='Download' download><i class='fa fa-download' aria-hidden='true'></i></a>"
                $(canvas_div).append($compile(download_elem)($scope))

                var slider_container = "<slider-range metrics='selectedMetrics' metric-index='" + index + "' ranges='ranges' format-date='formatDate(x)' filter-by-date='filterByDate(chartPanel, minLimit, maxLimit)' update-url='updateURL()' get-environment-ids='getEnvironmentIds()' value-min='" + min_value + "' value-max='" + max_value + "'></slider-range>"
                elem = $compile(slider_container)($scope)
                $(target).append(elem)

                var date_limit_container = "<div class='slider-limits'><div class='pull-left'><i class='fa fa-caret-right'></i> " + (new Date(metric.chart.minDate * 1000)).toISOString().slice(0,10) + "</div><div class='pull-right'>" + (new Date(metric.chart.maxDate * 1000)).toISOString().slice(0,10) + " <i class='fa fa-caret-left'></i></div></div>"
                elem = $compile(date_limit_container)($scope)
                $(target).append(elem)

                $('[data-toggle="tooltip"]').tooltip()
            }
        })
    }

    $scope.filterByDate = function(chartPanel, minLimit, maxLimit) {
        _.each(chartPanel.scatterChart.data.datasets, function(dataset) {
            var key = dataset.label.replace(/^:(low|high):/, '')
            dataset.data = $scope.filterData(
                chartPanel.data[key],
                minLimit,
                maxLimit,
                dataset.yidx
            )
        })
    }

    $scope.updateURL = function() {
        var search_location = {
            environment: $scope.getEnvironmentIds(),
            metric: $scope.getMetricIds()
        }
        _.each($scope.selectedMetrics, function(metric) {
            if (typeof $scope.ranges[metric.name] !== 'undefined' && $scope.ranges[metric.name].length > 0) {
                var range = $scope.ranges[metric.name][0] + "," +
                    $scope.ranges[metric.name][1]
                search_location["range_" + metric.name] = range
            }
        })

        $location.search(search_location)
    }

    $scope.update = function() {
        $scope.updateURL()
        $scope.download(function() {
            $scope.redraw()
        })
    }

    $scope.initPage = function() {

        var params = $location.search()

        var colors = [
            ['#4e9a06', '#8ae234', '#dcf6c2'], // Green
            ['#204a87', '#729fcf', '#cbdbed'], // Blue
            ['#563c66', '#ad7fa8', '#e4d4e2'], // Purple
            ['#a40000', '#ef2929', '#fabebe'], // Red
            ['#c4a000', '#fce94f', '#fef6ba'], // Yellow
            ['#ce5c00', '#fcaf3e', '#fee2ba'], // Orange
            ['#8f9502', '#e9b9ce', '#f6e2c2'], // Light brown
            ['#2e3436', '#888a85', '#d3d7cf']  // Dark Gray
        ];

        $scope.environments = DATA.environments
        _.each($scope.environments, function(environment, index) {
            var i = index % colors.length
            environment.line_color = colors[i][0]
            environment.fill_color = colors[i][1]
            environment.range_color = colors[i][2]
        })
        _.each(_.castArray(params.environment), function(param) {
            var env = _.find($scope.environments, function(env)  { return env.name == param})
            if (env) {
                env.selected = true
            }
        })

        $scope.metrics = DATA.metrics
        _.each($scope.metrics, function(metric) {
            if (!metric.label) {
                metric.label = metric.name
            }
        })
        $scope.selectedMetrics = _.filter($scope.metrics, function(metric) {
            var found = _.find(_.castArray(params.metric), function(param) { return param == metric.name })
            return found
        })

        $scope.ranges = {}
        _.each($scope.selectedMetrics, function(metric) {
            if (params["range_" + metric.name]) {
                var range_params = params["range_" + metric.name].split(",")
                if (range_params[0] < 0 || range_params[1] > 100 || range_params[0] > range_params[1] - 4) {
                    $scope.ranges[metric.name] = Array()
                } else {
                    $scope.ranges[metric.name] = range_params
                }
            } else {
                $scope.ranges[metric.name] = Array()
            }
        })

        $scope.data = DATA.data
        $scope.project = DATA.project
        $scope.calculate_max_results()

        $scope.redraw()

        // Initialize chart on all environments if there's no user set params.
        var selectedEnvs = $scope.getEnvironmentIds()
        if (selectedEnvs.length == 0 && $scope.selectedMetrics.length == 0) {
            $scope.toggleEnvironments()
            $scope.addMetric(_.find($scope.metrics, function(m) {return m.name == ":summary:"}))
        }
    }

    $scope.filterData = ChartPanel.filterData
    $scope.formatDate = ChartPanel.formatDate

    $scope.calculate_max_results = function() {
        for (var metric in $scope.data) {
            var max_count = 0
            for (var env_name in $scope.data[metric]) {
                if ($scope.data[metric][env_name].length > max_count) {
                    max_count =  $scope.data[metric][env_name].length
                }
            }
            $scope.data[metric]['max_count'] = max_count
        }
    }

    $scope.toggleFullScreen = function (elem_id) {
        var elem = document.getElementById(elem_id) || document.documentElement;
        if (!document.fullscreenElement && !document.mozFullScreenElement &&
            !document.webkitFullscreenElement && !document.msFullscreenElement) {
            if (elem.requestFullscreen) {
                elem.requestFullscreen();
            } else if (elem.msRequestFullscreen) {
                elem.msRequestFullscreen();
            } else if (elem.mozRequestFullScreen) {
                elem.mozRequestFullScreen();
            } else if (elem.webkitRequestFullscreen) {
                elem.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            } else if (document.mozCancelFullScreen) {
                document.mozCancelFullScreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            }
        }
    }

    $scope.downloadChartImage = function (target_id, button_id) {
        var image_url = document.getElementById(target_id).toDataURL('image/jpeg', 1.0);
        var download_button = document.getElementById(button_id);
        download_button.href = image_url;
    }

    $scope.initPage()
}

export {
    ChartSlider,
    ChartPanel, 
    ChartsController
}
