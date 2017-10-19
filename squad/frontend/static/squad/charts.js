var app = angular.module('SquadCharts', []);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

function ChartsController($scope, $http, $location) {

    var ChartPanel = function(metric, data) {
        this.metric = metric
        this.data = data
    }

    ChartPanel.prototype.draw = function(target) {
        var metric = this.metric
        var data = this.data
        var environments = _.filter($scope.environments, function(env) {
            return env.selected
        })

        var datasets = _.map(environments, function(env) {
            return {
                label: env.name,
                fill: false,
                borderWidth: 2,
                pointRadius: 1,
                lineTension: 0,
                backgroundColor: env.fill_color,
                borderColor: env.line_color,
                data: _.map(data[env.name], function(point) {
                    return { x: point[0], y: point[1], build_id: point[2] }
                })
            }
        })

        var ctx = document.createElement('canvas')
        target.appendChild(ctx)

        var formatDate = function(x) {
            // Javascript Date() takes milliseconds and x
            // is seconds, so multiply by 1000
            return (new Date(x * 1000)).toISOString().slice(0,10)
        }

        var scatterChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: datasets
            },
            options: {
                title: {
                    display: true,
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
        $scope.update()
    }

    $scope.removeMetric = function(metric) {
        _.remove($scope.selectedMetrics, function(m) {
            return m.name == metric.name
        })
        var chart_div = document.getElementById('metric-' + metric.name)
        chart_div.remove()
        metric.drawn = false
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
                    document.getElementById('charts').appendChild(target)
                }

                chart.draw(target)
                metric.drawn = true
            }
        })
    }

    $scope.updateURL = function() {
        $location.search({
            environment: $scope.getEnvironmentIds(),
            metric: $scope.getMetricIds()
        })
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

        $scope.data = DATA.data
        $scope.project = DATA.project

        $scope.redraw()
    }

    $scope.initPage()
}

app.controller(
    'ChartsController',
    [
        '$scope',
        '$http',
        '$location',
        ChartsController
    ]
);


