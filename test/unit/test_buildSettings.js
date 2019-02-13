import {BuildSettingsController} from '../../squad/frontend/static/squad/controllers/buildSettings.js'

var app = angular.module('buildSettingsApp', [])
app.controller(
    'BuildSettingsController',
    [
        '$scope',
        '$http',
        'build',
        BuildSettingsController
    ]
)

describe("BuildSettingsController", function () {

    beforeEach(module("buildSettingsApp"))

    var $controller, $rootScope, $compile

    beforeEach(inject(function(_$controller_, _$rootScope_, _$compile_){
        $controller = _$controller_
        $rootScope = _$rootScope_
        $compile = _$compile_
    }));

    describe("$scope.updateBuild", function () {

        var $scope, $httpBackend, build, controller, alertBox

        beforeEach(function() {
            $scope = $rootScope.$new()
            build = {
                "id": 1,
                "keep_data": true
            }

            controller = $controller('BuildSettingsController', {
                $scope: $scope,
                build: build
            })
        })

        beforeEach(inject(function($injector) {
            $httpBackend = $injector.get('$httpBackend')
        }))

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation()
            $httpBackend.verifyNoOutstandingRequest()
        })

        it('tests when updateBuild function succeeds', function () {
            $httpBackend.whenPATCH("/api/builds/1/").respond(200, {
                id: 1, keep_data: false
            })

            $scope.keep_data = false

            $scope.updateBuild()
            $httpBackend.flush()

            expect($scope.alert_type).toBe('success')
            expect($scope.keep_data).toBe(false)
            expect($scope.build.keep_data).toBe(false)
        })

        it('tests when updateBuild fails', function () {
            $httpBackend.whenPATCH("/api/builds/1/").respond(401, {
                "keep_data": ["invalid value"]
            })

            $scope.keep_data = false

            $scope.updateBuild()
            $httpBackend.flush()

            expect($scope.alert_type).toBe('danger')
            expect($scope.alert_message.indexOf('invalid value')).not.toBe(-1)
            expect($scope.build.keep_data).toBe(true)
        })
    })
})
