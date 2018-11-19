describe("ResubmitController", function () {

    beforeEach(module("Build"));

    var $controller;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe("$scope.resubmit", function () {

        var $httpBackend;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('ResubmitController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        beforeEach(inject(function($injector) {
            $timeout = $injector.get('$timeout');
            $httpBackend = $injector.get('$httpBackend');
            $httpBackend.whenGET("/api/resubmit/1").respond(
                200, ["submitted"]);
            $httpBackend.whenGET("/api/forceresubmit/1").respond(
                401, ["error"]);
        }));

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('tests resubmit function when response is OK', function () {
            $scope.resubmit(1, false)
            $httpBackend.flush();

            $timeout.flush();
            $timeout.verifyNoPendingTasks();

            expect($scope.error).toBe(false)
            expect($scope.loading).toBe(false)
            expect($scope.done).toBe(true)
        });

        it('tests resubmit function when response is error', function () {
            spyOn(window, 'alert')
            $scope.resubmit(1, true)
            $httpBackend.flush();

            expect(window.alert).toHaveBeenCalledWith('There was an error while resubmitting.\nStatus = 401 (complete)');
            expect($scope.error).toBe(true)
            expect($scope.done).toBe(true)
            expect($scope.loading).toBe(false)
        });
    });
});
