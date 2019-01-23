import {ChartSlider, ChartPanel, ChartsController} from './controllers/charts.js'

var app = angular.module('SquadCharts', []);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

app.factory('ChartPanel', ChartPanel);

app.controller(
    'ChartsController',
    [
        '$scope',
        '$http',
        '$location',
        '$compile',
        'ChartPanel',
        ChartsController
    ]
);

app.directive('sliderRange', ['$document', ChartSlider]);
