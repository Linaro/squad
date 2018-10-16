var app = angular.module('SquadCharts', []);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

function ChartsController($scope, $http, $location, $compile) {

    var ChartPanel = function(metric, data) {
        this.metric = metric
        this.data = data
        this.updateMinDate($scope.getEnvironmentIds())
        this.updateMaxDate($scope.getEnvironmentIds())
    }

    ChartPanel.prototype.updateMinDate = function(environmentIds) {
        // This assumes that the metrics data is sorted by date.
        var minDate = Math.round(new Date() / 1000)
        var data = this.data
        _.each(environmentIds, function(name) {
            if (data[name][0][0] < minDate) {
                minDate = data[name][0][0]
            }
        })

        this.minDate = minDate
    }

    ChartPanel.prototype.updateMaxDate = function(environmentIds) {
        // This assumes that the metrics data is sorted by date.
        var maxDate = 0
        var data = this.data
        _.each(environmentIds, function(name) {
            if (data[name][data[name].length-1][0] > maxDate) {
                maxDate = data[name][data[name].length-1][0]
            }
        })
        this.maxDate = maxDate
    }

    ChartPanel.prototype.draw = function(target) {
        var metric = this.metric
        var data = this.data
        var minDate = this.minDate
        var maxDate = this.maxDate

        var environments = _.filter($scope.environments, function(env) {
            return env.selected
        })

        var datasets = _.map(environments, function(env) {
            var minCoefficient = $scope.slider.defaultResultsLimit
            var maxCoefficient = 1
            if (typeof $scope.ranges[metric.name] !== 'undefined' && $scope.ranges[metric.name].length > 0) {
                minCoefficient = $scope.ranges[metric.name][0] / 100
                maxCoefficient = $scope.ranges[metric.name][1] / 100
            }

            minLimit = minDate + Math.round((maxDate - minDate)*minCoefficient)
            maxLimit = minDate + Math.round((maxDate - minDate)*maxCoefficient)

            return {
                label: env.name,
                fill: false,
                borderWidth: 2,
                pointRadius: 1,
                lineTension: 0,
                backgroundColor: env.fill_color,
                borderColor: env.line_color,
                data: $scope.filter_data(data[env.name], minLimit, maxLimit)
            }
        })

        var ctx = document.createElement('canvas')
        target.appendChild(ctx)

        var formatDate = function(x) {
            // Javascript Date() takes milliseconds and x
            // is seconds, so multiply by 1000
            // Check if x 'defaults' to [-1, 1] range which means there are no
            // results, and in that case return an empty string.
            if (x <= 1 && x >= -1) {
                return ""
            } else {
                return (new Date(x * 1000)).toISOString().slice(0,10)
            }
        }

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
                            tooltip = t[0]
                            dataset = data_objects.datasets[tooltip.datasetIndex]
                            data_point = build_id = dataset.data[tooltip.index]
                            return formatDate(data_point.x)
                        },
                        beforeBody: function(t, data_objects) {
                            tooltip = t[0]
                            dataset = data_objects.datasets[tooltip.datasetIndex]
                            data_point = build_id = dataset.data[tooltip.index]
                            return "Build #" + data_point.build_id
                        }
                    }
                },
                animation: {
                    duration: 0,
                },
                scales: {
                    yAxes: [{
                        ticks: {
                            max: metric.max,
                            min: metric.min
                        }
                    }],
                    xAxes: [{
                        type: 'linear',
                        position: 'bottom',
                        ticks: {
                            callback: formatDate
                        }
                    }]
                }
            }
        });

        ctx.onclick = function(evt) {
            var point = scatterChart.getElementAtEvent(evt)[0]
            if (point) {
                var data_point = datasets[point._datasetIndex].data[point._index]
                var build = data_point.build_id
                window.location.href= '/' + $scope.project + '/build/' + build + '/'
            }
        }

        this.scatterChart = scatterChart
    }

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
        params = {
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
        _.each($scope.selectedMetrics, function(metric) {
            if (! metric.drawn) {
                var data = $scope.data[metric.name]
                var chart = new ChartPanel(metric, data)

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
                    "</div><div class='h4 pull-right'><button " +
                    "ng-click='toggleFullScreen(\"" + target_id +
                    "\")' class='btn btn-default btn-xs' " +
                    "title='Toggle Fullscreen'><i class='fa fa-expand' " +
                    "aria-hidden='true'></i></button></div></div>"
                var elem = $compile(title_container)($scope)
                $(target).append(elem)

                var min_value = $scope.slider.defaultResultsLimit * 100;
                var max_value = $scope.slider.rangeMax
                if (typeof $scope.ranges[metric.name] !== 'undefined' && $scope.ranges[metric.name].length > 0) {
                    min_value = $scope.ranges[metric.name][0]
                    max_value = $scope.ranges[metric.name][1]
                }

                chart.draw(target)
                metric.chart = chart
                metric.drawn = true

                var slider_container = "<slider-range metrics='selectedMetrics' ranges='ranges' filter-data='filter_data(data, minLimit, maxLimit)' update-url='updateURL()' value-min='" + min_value + "' value-max='" + max_value + "'></slider-range>"
                elem = $compile(slider_container)($scope)
                $(target).append(elem)

                var date_limit_container = "<div class='slider-limits'><div class='pull-left'><i class='fa fa-caret-right'></i> " + (new Date(metric.chart.minDate * 1000)).toISOString().slice(0,10) + "</div><div class='pull-right'>" + (new Date(metric.chart.maxDate * 1000)).toISOString().slice(0,10) + " <i class='fa fa-caret-left'></i></div></div>"
                elem = $compile(date_limit_container)($scope)
                $(target).append(elem)
            }
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
            ['#4e9a06', '#8ae234'], // Green
            ['#204a87', '#729fcf'], // Blue
            ['#563c66', '#ad7fa8'], // Purple
            ['#a40000', '#ef2929'], // Red
            ['#c4a000', '#fce94f'], // Yellow
            ['#ce5c00', '#fcaf3e'], // Orange
            ['#8f9502', '#e9b9ce'], // Light brown
            ['#2e3436', '#888a85']  // Dark Gray
        ];

        $scope.environments = DATA.environments
        _.each($scope.environments, function(environment, index) {
            i = index % colors.length
            environment.line_color = colors[i][0]
            environment.fill_color = colors[i][1]
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
    }

    $scope.filter_data = function(data, minLimit, maxLimit) {
        var current_data = _.filter(data, function(point) {
            return point[0] > minLimit && point[0] < maxLimit
        }).map(function(point){
            return {
                x: point[0],
                y: point[1],
                build_id: point[2]
            }
        })

        return current_data
    }

    $scope.calculate_max_results = function() {
        for (metric in $scope.data) {
            var max_count = 0
            for (env_name in $scope.data[metric]) {
                if ($scope.data[metric][env_name].length > max_count) {
                    max_count =  $scope.data[metric][env_name].length
                }
            }
            $scope.data[metric]['max_count'] = max_count
        }
    }

    $scope.toggleFullScreen = function (elem_id) {
        elem = document.getElementById(elem_id) || document.documentElement;
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

    $scope.slider = {
        defaultResultsLimit: 0.8,
        rangeMax: 100
    };

    $scope.initPage()
}

app.controller(
    'ChartsController',
    [
        '$scope',
        '$http',
        '$location',
        '$compile',
        ChartsController
    ]
);

app.directive('sliderRange', ['$document',function($document) {

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

    return {
        template: '<div class="slider horizontal">' +
            '<div class="range" ng-mousedown="mouseDown($event)"></div>' +
            '<i class="handle min btn btn-xs btn-default fa fa-caret-right" ' +
            'aria-hidden="true" ng-mousedown="mouseDown($event)"></i>' +
            '<i class="handle max btn btn-xs btn-default fa fa-caret-left" ' +
            'aria-hidden="true" ng-mousedown="mouseDown($event)"></i>' +
            '</div>',
        replace: true,
        restrict: 'E',
        scope: {
            valueMin: "=",
            valueMax: "=",
            metrics: "=metrics",
            ranges: "=ranges",
            updateUrl: "&",
            filterData: "&",
        },
        link: function postLink(scope, element, attrs) {
            // Initilization
            var dragging = false
            var startPointX = 0
            var xMin = scope.valueMin
            var xMax = scope.valueMax
            moveHandle(findElement(element, "min"), xMin)
            moveHandle(findElement(element, "max"), xMax)
            moveRange(element, xMin, xMax)

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
                    }
                    moveRange(element, xMin, xMax)

                    // Update chart.
                    var current = _.find(scope.metrics, function(m) {
                        return m.name == element.parent().attr('id').replace("metric-", "")
                    })

                    var minDate = current.chart.minDate
                    var maxDate = current.chart.maxDate
                    var minLimit = minDate +
                        Math.round((maxDate - minDate) * (xMin / 100))
                    var maxLimit = minDate +
                        Math.round((maxDate - minDate) * (xMax / 100))

                    _.each(current.chart.scatterChart.data.datasets, function(dataset) {
                        dataset.data = scope.filterData({
                            data: current.chart.data[dataset.label],
                            minLimit: minLimit,
                            maxLimit: maxLimit
                        })
                    });
                    current.chart.scatterChart.update()

                    // Update range.
                    scope.ranges[current.name][0] = Math.round(xMin)
                    scope.ranges[current.name][1] = Math.round(xMax)
                });

                $document.mouseup(function() {
                    scope.updateUrl()
                    scope.$apply()
                    dragging = false
                    $document.unbind('mousemove')
                });
            };
        }
    };
}]);
