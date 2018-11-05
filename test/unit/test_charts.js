describe("ChartsController", function () {

    beforeEach(module("SquadCharts"));

    var $controller, chartsController;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe("ChartPanel", function () {

        DATA = {}
        beforeEach(function() {
            metric = {"max":100,"name":":tests:","min":0,"label":"Test pass %"}
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
            environments = ["hi6220-hikey", "x86"]
        });

        beforeEach(inject(function($injector) {
            ChartPanel = $injector.get('ChartPanel')
        }));

        it('tests if minDate works on empty environments', function () {
            // Constructor calls updateMinDate
            chartPanel = new ChartPanel(metric, data, [])
            expect(chartPanel.minDate).toEqual(Math.round(new Date() / 1000))
        });

        it('tests if minDate works on empty data', function () {
            data["hi6220-hikey"] = []
            // Constructor calls updateMinDate
            chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.minDate).toEqual(Math.round(new Date() / 1000))
        });

        it('tests if minDate works', function () {
            // Constructor calls updateMinDate
            chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.minDate).toEqual(1498242465)
        });

        it('tests if maxDate works on empty environments', function () {
            // Constructor calls updateMaxDate
            chartPanel = new ChartPanel(metric, data, [])
            expect(chartPanel.maxDate).toEqual(0)
        });

        it('tests if maxDate works on empty data', function () {
            data["hi6220-hikey"] = []
            // Constructor calls updateMaxDate
            chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.maxDate).toEqual(0)
        });

        it('tests if maxDate works', function () {
            // Constructor calls updateMaxDate
            chartPanel = new ChartPanel(metric, data, environments)
            expect(chartPanel.maxDate).toEqual(1498422468)
        });

        it('tests if filterData works on empty data', function () {
            data["hi6220-hikey"] = []
            filtered_data = ChartPanel.filterData(
                data, 1498307267, 1498422458)
            expect(filtered_data.length).toEqual(0)
        });

        it('tests if filterData works on ambiguous limits', function () {
            filtered_data = ChartPanel.filterData(
                data, 1498422458, 1498307267)
            expect(filtered_data.length).toEqual(0)
        });

        it('tests if filterData works', function () {
            filtered_data = ChartPanel.filterData(
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
            filtered_data = ChartPanel.filterData(
                data, 1498422458, 1498307267)
            expect(filtered_data.length).toEqual(0)
        });

    });

    describe('$scope.getEnvironmentIds', function() {
        var $scope, controller, $attrs;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            URL = {};
            controller = $controller('ChartsController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        it('checks if returns environment names correctly', function() {
            $scope.environments = [
                {name: "hi6220-hikey", line_color: "#4e9a06", selected: true},
                {name: "x86", line_color: "#204a87", selected: true},
                {name: "juno-r2", line_color: "#563c66"},
                {name: "x15", line_color: "#a40000", selected: true}
            ]
            env_ids = $scope.getEnvironmentIds()
            expect(env_ids.length).toEqual(3)
            expect($scope.getEnvironmentIds()).toEqual(
                ["hi6220-hikey", "x86", "x15"])
        });

    });

    describe('$scope.download', function() {
        var $scope, controller, $attrs, $httpBackend;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            URL = {};
            controller = $controller('ChartsController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });

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
               $scope.selectedMetrics = ["Test pass %", "some_metric"]
               $scope.project = "test_project"

               $scope.download(obj.callback)

               expect(obj.callback).toHaveBeenCalled()
               expect($scope.data).toBeUndefined()
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
