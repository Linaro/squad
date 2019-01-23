import {FilterController} from '../../squad/frontend/static/squad/controllers/filter.js'

angular.module('filterApp', []).controller(
    'FilterController',
    [
        '$scope',
        '$attrs',
        '$location',
        FilterController
    ]
);

describe('FilterController', function() {
    beforeEach(module('filterApp'));

    var $controller;

    beforeEach(inject(function(_$controller_){
        $controller = _$controller_;
    }));

    describe('$scope.update', function() {
        var $scope, controller, $attrs, $location, dummyElement, URL;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            $location = "";
            controller = $controller('FilterController', {
                $scope: $scope,
                $attrs: $attrs,
                $location: $location
            });

            URL = $scope.URL;
        });

        it('checks if URL variable is properly updated', function() {
            $attrs.param = 'filter-tests'
            $scope.filter = 'test'
            $scope.details_visible = {
                'element_id': true
            }
            $scope.update();
            expect(URL).toEqual({"filter-tests": 'test', "details": 'element_id'});
        });

        it('checks if URL variable is properly updated if no visible elements', function() {
            $attrs.param = 'filter-tests'
            $scope.filter = 'test'
            $scope.details_visible = {}
            $scope.update();
            expect(URL).toEqual({"filter-tests": 'test', "details": ''});
        });

        it('checks if URL variable is properly updated if no filter', function() {
            $attrs.param = 'filter-tests'
            $scope.filter = ''
            $scope.details_visible = {
                'element_id': true
            }
            $scope.update();
            expect(URL).toEqual({"filter-tests": '', "details": 'element_id'});
        });
    });

    describe('$scope.match', function() {
        var $scope, controller, $attrs, $location, dummyElement;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            controller = $controller('FilterController', {
                $scope: $scope,
                $attrs: $attrs
            });

            dummyElement = document.createElement('div');
            dummyElement.id = 'div_id';
            document.getElementById = jasmine.createSpy(
                'HTML Element').and.returnValue(dummyElement);
        });

        it('checks if the filter matches the correct string', function() {
            $scope.filter = 'some text';
            dummyElement.textContent = 'this matches some text';
            expect($scope.match('div_id')).toBe(true);
        });

        it('checks if the filter does not match the string', function() {
            $scope.filter = 'some text';
            dummyElement.textContent = 'this does not match';
            expect($scope.match('div_id')).toBe(false);
        });

        it('checks if function returns true for empty/undefined filter',
           function() {
               expect($scope.match('div_id')).toBe(true);
               $scope.filter = '';
               expect($scope.match('div_id')).toBe(true);
           });
    });

    describe('$scope.toggle_details', function() {
        var $scope, controller, $attrs, $location, dummyElement;

        beforeEach(function() {
            $scope = {};
            $attrs = {};
            controller = $controller('FilterController', {
                $scope: $scope,
                $attrs: $attrs
            });

            var dummyElement = document.createElement('div');
            dummyElement.id = 'div_id';
            document.getElementById = jasmine.createSpy(
                'HTML Element').and.returnValue(dummyElement);
        });

        it('checks if it adds visible value to dict', function() {
            $scope.details_visible = {};
            $scope.toggle_details("element_id");
            expect($scope.details_visible["element_id"]).toBe(true);
        });

        it('checks if it removes visible value from dict', function() {
            $scope.details_visible = {"element_id": true};
            $scope.toggle_details("element_id");
            expect($scope.details_visible["element_id"]).toBeUndefined();
        });
    });
});

