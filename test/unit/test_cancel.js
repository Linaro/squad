import {CancelController} from '../../squad/frontend/static/squad/controllers/cancel.js'

angular.module('cancelApp', []).controller(
    'CancelController',
    [
        '$scope',
        '$http',
        '$location',
        '$timeout',
        CancelController
    ]
);

describe("CancelController", function () {

    beforeEach(module("cancelApp"));

    var $controller;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe("$scope.cancel", function () {

        var $scope, $attrs, $location, $httpBackend, $timeout, controller;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('CancelController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        beforeEach(inject(function($injector) {

            $timeout = $injector.get('$timeout');
            $httpBackend = $injector.get('$httpBackend');
            $httpBackend.whenPOST("/api/testjobs/1/cancel/").respond(
                200, ["cancelled"]);
            $httpBackend.whenPOST("/api/testjobs/2/cancel/").respond(
                401, ["error"]);
        }));

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('tests cancel function when response is OK', function () {
            $scope.cancel(1)
            $httpBackend.flush();

            $timeout.flush();
            $timeout.verifyNoPendingTasks();

            expect($scope.error).toBe(false)
            expect($scope.loading).toBe(false)
            expect($scope.done).toBe(true)
        });

        it('tests cancel function when response is error', function () {
            spyOn(window, 'alert')
            $scope.cancel(2)
            $httpBackend.flush();

            expect(window.alert).toHaveBeenCalledWith('There was an error while cancelling.\nStatus = 401 (complete)');
            expect($scope.error).toBe(true)
            expect($scope.done).toBe(true)
            expect($scope.loading).toBe(false)
        });
    });
});
