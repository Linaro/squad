import {CompareController} from '../../squad/frontend/static/squad/controllers/compare.js'

var app = angular.module('compareApp', []);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

app.controller(
    'CompareController',
    [
        '$scope',
        '$http',
        '$location',
        CompareController
    ]
);

describe("CompareController", function () {

    beforeEach(module("compareApp"));

    var $controller;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe("$scope.updateKnownIssue", function () {

        var $httpBackend, $scope, $attrs, $location, controller;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('CompareController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        beforeEach(inject(function($injector) {
            $httpBackend = $injector.get('$httpBackend');
            // Ignore requests from select2 for now.
            $httpBackend.whenGET(/.*?api\/projects?.*/g).respond(
                200, []);

            $httpBackend.whenGET(/.*?api\/knownissues?.*/g).respond(
                200, {results: "1", count: 1});

            // Ignore rest of select 2 requests.
            $httpBackend.whenGET(/.*?api\/suitemetadata?.*/g).respond(
                200, {results: [{id: "1"}]});
            $httpBackend.whenGET(/.*?api\/suitemetadata?.*/g).respond(
                200, {results: [{id: "1"}]});
        }));

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('tests if result is correct with no selected suites and tests',
           function () {
               $scope.updateKnownIssue()
               $httpBackend.flush();

               expect($scope.knownIssues).toBeUndefined()
               expect($scope.hasKnownIssue).toBe(false)
        });

        it('tests if it sets scope variables correctly', function () {
            $scope.selectedSuite = ""
            $scope.selectedTest = ""

            $scope.updateKnownIssue()
            $httpBackend.flush();

            expect($scope.knownIssues).toBe("1")
            expect($scope.hasKnownIssue).toBe(true)
        });
    });

    describe("$scope.updateURL", function () {
        var $scope, $attrs, $location, controller;
        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $scope.$evalAsync = function() {}
            controller = $controller('CompareController', {
                $scope: $scope,
                $attrs: $attrs,
            });
        });

        beforeEach(inject(function (_$location_) {
            $location = _$location_;
        }));


        it('tests if search path is correct for no project', function () {
            $scope.updateURL()
            expect($location.search()).toEqual({project: []})
        });

        it('tests if search path is correct for projects', function () {
            $scope.selectedProjects = [{id: 1}, {id: 2}]
            $scope.updateURL()
            expect($location.search()).toEqual({project: [1,2]})
        });

        it('tests if search path is correct for projects and suite',
           function () {
               $scope.selectedProjects = [{id: 1}, {id: 2}]
               $scope.selectedSuite = "suite1"
               $scope.updateURL()
               expect($location.search()).toEqual({
                   project: [1,2],
                   suite: "suite1"
               })
        });

        it('tests if search path is correct for projects and suite and tests',
           function () {
               $scope.selectedProjects = [{id: 1}, {id: 2}]
               $scope.selectedSuite = "suite1"
               $scope.selectedTest = "test1"
               $scope.updateURL()
               expect($location.search()).toEqual({
                   project: [1,2],
                   suite: "suite1",
                   test: "test1"
               })
        });
    });

    describe("$scope.addProject", function () {
        var $scope, $attrs, controller;
        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $scope.$evalAsync = function() {}
            controller = $controller('CompareController', {
                $scope: $scope,
                $attrs: $attrs,
            });
        });

        it('checks the value of seletedProjects if the project already exists',
           function() {
               var project = {id: 1}
               var selected = [{id: 1}, {id: 2}]
               $scope.selectedProjects = selected
               $scope.addProject(project)
               expect($scope.selectedProjects).toEqual(selected)
        });

        it('checks the value of seletedProjects and showProgress',
           function() {
               var project = {id: 1, invokeCompare: true}
               $scope.selectedProjects = [{id: 2, invokeCompare: true}]
               $scope.selectedTest = {}
               $scope.selectedSuite = {}
               $scope.addProject(project)
               expect($scope.selectedProjects).toEqual([{id: 2, invokeCompare: true}, {id: 1, invokeCompare: true}])
               expect($scope.showProgress[project.id]).toBe(true)
               expect($scope.showResults).toBe(true)
        });
    });

    describe("$scope.removeProject", function () {
        var $scope, $attrs, $location, controller;
        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $scope.$evalAsync = function() {}
            controller = $controller('CompareController', {
                $scope: $scope,
                $attrs: $attrs,
            });
        });

        it('checks the value of seletedProjects after removal',
           function() {
               var project = {id: 1}
               $scope.selectedProjects = [{id: 1}, {id: 2}]
               $scope.removeProject(project)
               expect($scope.selectedProjects).toEqual([{id: 2}])
        });
    });


    describe("$scope.loadMoreData", function () {
        var $scope, $attrs, $location, $httpBackend, controller;
        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('CompareController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        beforeEach(inject(function($injector) {
            $httpBackend = $injector.get('$httpBackend');
            // Ignore requests from select2 for now.
            $httpBackend.whenGET(/.*?api\/projects?.*/g).respond(
                200, []);

            $httpBackend.whenGET(/.*?project_test_results?.*/g).respond(
                200, ["data"]);

            // Ignore rest of select 2 requests.
            $httpBackend.whenGET(/.*?api\/suitemetadata?.*/g).respond(
                200, {results: [{id: "1"}]});
            $httpBackend.whenGET(/.*?api\/suitemetadata?.*/g).respond(
                200, {results: [{id: "1"}]});
            $httpBackend.whenGET(/.*?api\/knownissues?.*/g).respond(
                200, {results: "1", count: 1});
        }));

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('tests if it sets $scope variables correctly', function () {
            $scope.selectedProjects = [{id: 1, url: 'project_'}]
            $scope.projectBuilds = {1: "build_"}
            $scope.loadedLimits = {1: 0}
            $scope.selectedSuite = 'suite1'
            $scope.selectedTest = 'test1'

            $scope.loadMoreData(1)
            $httpBackend.flush()

            expect($scope.projectBuilds[1]).toEqual("build_data")
            expect($scope.loadedLimits[1]).toEqual(10)
        });
    });
});
