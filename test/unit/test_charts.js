import {ChartPanel as _ChartPanel, ChartsController} from '../../squad/frontend/static/squad/controllers/charts.js'

var app = angular.module('chartsApp', []);

app.value('DATA', {});
app.factory('ChartPanel', ['$http', 'DATA', _ChartPanel]);

app.controller(
    'ChartsController',
    [
        '$scope',
        '$http',
        '$location',
        '$compile',
        'ChartPanel',
        'DATA',
        ChartsController
    ]
);

describe("Charts", function () {

    beforeEach(module("chartsApp"));

    describe("ChartPanel", function () {
        var metric, data, environments, ChartPanel
        var metric_boot, data_boot
        beforeEach(function() {
            metric = {"max":100,"name":":tests:","min":0,"label":"Test pass %"}
            metric_boot = {"name":"boot/time-hi6220-hikey-r2"}
            data = {
                "hi6220-hikey":
                [
                    [1498242465, 98, "v4.12-rc6-102-ga38371c"],
                    [1498244093, 98, "v4.12-rc6-81-g8d829b9"],
                    [1498307267, 98, "v4.12-rc6-158-g94a6df2"],
                    [1498321658, 98, "v4.12-rc6-160-gf65013d"],
                    [1498350465, 98, "v4.12-rc6-167-gbb9b8fd"],
                    [1498422458, 98, "v4.12-rc6-191-ga4fd8b3"],
                    [1498422468, 98, "v4.12-rc6-175-g412572b"]
                ]
            }
            data_boot = {
                "hi6220-hikey_4.14":
                [
                    [1528282625, 4.25, "3", "", 1383135, "False"],
                    [1528772626, 4.27, "3", "", 1383138, "False"],
                    [1528274629, 8.25, "3", "", 1383139, "False"],
                    [1528292621, 2.26, "3", "", 1383140, "False"],
                    [1528217620, 1.75, "3", "", 1383141, "False"],
                    [1528288624, 9.26, "3", "", 1383142, "False"],
                    [1528202625, 1.86, "3", "", 1383144, "False"],
                ]
            }
            environments = ["hi6220-hikey", "hi6220-hikey_4.14", "x86"]
        });

        beforeEach(inject(function($injector) {
            ChartPanel = $injector.get('ChartPanel')
        }));

        it('tests if minDate works on empty environments', function () {
            // Constructor calls updateMinDate
            var chartPanel = new ChartPanel(metric, data, [])
            expect(chartPanel.minDate).toEqual(Math.round(new Date() / 1000))
        });

        it('tests if minDate works on empty data', function () {
            data["hi6220-hikey"] = []
            // Constructor calls updateMinDate
            var chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.minDate).toEqual(Math.round(new Date() / 1000))
        });

        it('tests if minDate works', function () {
            // Constructor calls updateMinDate
            var chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.minDate).toEqual(1498242465)
        });

        it('tests if maxDate works on empty environments', function () {
            // Constructor calls updateMaxDate
            var chartPanel = new ChartPanel(metric, data, [])
            expect(chartPanel.maxDate).toEqual(0)
        });

        it('tests if maxDate works on empty data', function () {
            data["hi6220-hikey"] = []
            // Constructor calls updateMaxDate
            var chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.maxDate).toEqual(0)
        });

        it('tests if maxDate works', function () {
            // Constructor calls updateMaxDate
            var chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.maxDate).toEqual(1498422468)
        });

        it('tests if filterData works on empty data', function () {
            data["hi6220-hikey"] = []
            var filtered_data = ChartPanel.filterData(
                data, 1498307267, 1498422458)
            expect(filtered_data.length).toEqual(0)
        });

        it('tests if filterData works on ambiguous limits', function () {
            var filtered_data = ChartPanel.filterData(
                data, 1498422458, 1498307267)
            expect(filtered_data.length).toEqual(0)
        });

        it('tests if filterData works', function () {
            var filtered_data = ChartPanel.filterData(
                data["hi6220-hikey"], 1498307267, 1498422458)
            expect(filtered_data.length).toEqual(4)
            expect(filtered_data).toEqual(
                [
                    {x: 1498307267, y: 98, build_id: "v4.12-rc6-158-g94a6df2"},
                    {x: 1498321658, y: 98, build_id: "v4.12-rc6-160-gf65013d"},
                    {x: 1498350465, y: 98, build_id: "v4.12-rc6-167-gbb9b8fd"},
                    {x: 1498422458, y: 98, build_id: "v4.12-rc6-191-ga4fd8b3"},
                ])
        });

        it('tests if filterData works on ambiguous limits', function () {
            var filtered_data = ChartPanel.filterData(
                data, 1498422458, 1498307267)
            expect(filtered_data.length).toEqual(0)
        });

        it('tests if draw works', function(){
            var envs = [{
                name: 'hi6220-hikey_4.14',
                fill_color: 'blue',
                line_color: 'black',
                selected: true
            }]
            var target = document.createElement('div')
            document.body.appendChild(target)

            var chartPanel = new ChartPanel(metric_boot, data_boot, environments)
            chartPanel.draw(target, envs)

            expect(target.getElementsByTagName('canvas').length).toEqual(1)
        })
    });

    describe('ChartsController', function(){
        var $controller, $scope, $attrs, $location, controller, DATA;

        beforeEach(inject(function(_$controller_){
            $controller = _$controller_;
        }));

        beforeEach(function() {
            DATA = {
                metrics: [
                    {'name': ':summary:', 'label': 'Summary of all metrics per build'},
                    {'min': 0, 'max': 100, 'name':
                     ':tests:', 'label': 'Test pass %'},
                    {'name': 'boot/time-hi6220-hikey'}
                ],
                data: {
                    'boot/time-hi6220-hikey': {
                        'hi6220-hikey_4.9': [
                            [1528282625, 4.62, '3', '', 1383125, 'False'],
                            [1528282626, 4.63, '3', '', 1383130, 'False'],
                            [1528282627, 4.62, '3', '', 1383131, 'False'],
                        ],
                    },
                    ':tests:': {
                        'hi6220-hikey_4.9': [
                            [1528282625, 100, '3', ''],
                            [1528293161, 99, '4', ''],
                            [1528299832, 99, '5', ''],
                        ],
                    },
                    ':summary:': {
                        'hi6220-hikey_4.9': [
                            [1528282625, 32.45, '3', ''],
                            [1528293161, 84.73, '4', ''],
                            [1528299832, 99.86, '5', ''],
                        ],
                    }
                }
            };

            var charts = document.createElement('div')
            charts.id = 'charts'
            document.body.appendChild(charts)

            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('ChartsController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location,
                DATA: DATA,
            });
        });

        describe('$scope.getEnvironmentIds', function() {

            it('checks if returns environment names correctly', function() {

                $scope.environments = [
                    {name: "hi6220-hikey", line_color: "#4e9a06", selected: true},
                    {name: "x86", line_color: "#204a87", selected: true},
                    {name: "juno-r2", line_color: "#563c66"},
                    {name: "x15", line_color: "#a40000", selected: true}
                ]

                var env_ids = $scope.getEnvironmentIds()
                expect(env_ids.length).toEqual(3)
                expect($scope.getEnvironmentIds()).toEqual(["hi6220-hikey", "x86", "x15"])
            });

        });

        describe('$scope.download', function() {
            var $httpBackend, responseData, obj

            beforeEach(function() {

                obj = {
                    callback: function(value) {}
                }
                spyOn(obj, 'callback')

                responseData =
                    {
                        "hi6220-hikey":
                        [
                            [1498242465, 98, "v4.12-rc6-102-ga38371c"],
                            [1498244093, 98, "v4.12-rc6-81-g8d829b9"],
                            [1498307267, 98, "v4.12-rc6-158-g94a6df2"],
                            [1498321658, 98, "v4.12-rc6-160-gf65013d"],
                            [1498350465, 98, "v4.12-rc6-167-gbb9b8fd"],
                            [1498422458, 98, "v4.12-rc6-191-ga4fd8b3"],
                            [1498422468, 98, "v4.12-rc6-175-g412572b"]
                        ]
                    }
            });

            beforeEach(inject(function($injector) {
                $httpBackend = $injector.get('$httpBackend');
                $httpBackend.whenGET(/.*?api\/data?.*/g).respond(
                    200, responseData);
            }));

            afterEach(function() {
                $httpBackend.verifyNoOutstandingExpectation();
                $httpBackend.verifyNoOutstandingRequest();
            });

            it('checks if $scope.data is undefined if environments is empty',
               function() {
                   $scope.environments = {}
                   $scope.data = {}
                   $scope.selectedMetrics = ["Test pass %", "some_metric"]
                   $scope.project = "test_project"

                   $scope.download(obj.callback)

                   expect(obj.callback).toHaveBeenCalled()
                   expect($scope.data).toEqual({})
               })

            it('checks if returns environment names correctly', function() {
                $scope.environments = [
                    {name: "hi6220-hikey", line_color: "#4e9a06", selected: true},
                    {name: "x86", line_color: "#204a87", selected: true},
                    {name: "juno-r2", line_color: "#563c66"},
                    {name: "x15", line_color: "#a40000", selected: true}
                ]
                $scope.selectedMetrics = ["Test pass %", "some_metric"]
                $scope.project = "test_project"

                $scope.download(obj.callback)
                $httpBackend.flush();

                expect(obj.callback).toHaveBeenCalled()
                expect(Object.keys($scope.data)).toEqual(Object.keys(responseData))
                expect($scope.data["hi6220-hikey"].length).toEqual(
                    responseData["hi6220-hikey"].length)
            });
        });
    });
});
