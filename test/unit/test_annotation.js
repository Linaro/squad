import {AnnotationController} from '../../squad/frontend/static/squad/controllers/annotation.js'

angular.module('annotationApp', []).controller(
    'AnnotationController',
    [
        '$scope',
        '$http',
        '$httpParamSerializerJQLike',
        AnnotationController
    ]
);

describe("AnnotationController", function () {

    beforeEach(module("annotationApp"));

    var $controller;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe("$scope.updateAnnotation", function () {

        var $scope, $attrs, $location, $httpBackend, controller;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";

            controller = $controller('AnnotationController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });
        });

        beforeEach(inject(function($injector) {
            $httpBackend = $injector.get('$httpBackend');
        }));

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('tests update function when adding annotation', function () {
            $httpBackend.whenPOST("/api/annotations/").respond(
                200, {id: 5});
            $scope.updateAnnotation(1)
            $httpBackend.flush();

            expect($scope.annotation_id).toBe(5)
        });

        it('tests update function when editing annotation', function () {
            $scope.annotation_id = 5
            $httpBackend.whenPUT(
                "/api/annotations/" + $scope.annotation_id + "/").respond(
                    200, {id: 5});
            $scope.updateAnnotation(1)
            $httpBackend.flush();

            expect($scope.annotation_id).toBe(5)

        });

        it('tests when update function returns error', function () {
            spyOn(window, 'alert')
            $httpBackend.whenPOST("/api/annotations/").respond(
                401, {detail: "some error"});
            $scope.updateAnnotation(1)
            $httpBackend.flush();
            expect(window.alert).toHaveBeenCalledWith('There was an error while editing annotation.\nMessage: some error');
        });
    });
});
