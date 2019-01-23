import {CompareController} from './controllers/compare.js'

var app = angular.module('SquadCompare', []);

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
