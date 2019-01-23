import {ChartSlider, ChartPanel, ChartsController} from './controllers/charts.js'
import {Config as appConfig} from './config.js'

var app = angular.module('SquadCharts', []);

appConfig(app, ['locationProvider', 'httpProvider']);

app.factory('ChartPanel', ['$http', ChartPanel]);

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
