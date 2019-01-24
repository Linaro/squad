import {ChartSlider, ChartPanel, ChartsController} from './controllers/charts.js'
import {Config as appConfig} from './config.js'

var app = angular.module('SquadCharts', []);

appConfig(app, ['locationProvider', 'httpProvider']);

app.value('DATA', window.DATA);

app.factory('ChartPanel', ['$http', 'DATA', ChartPanel]);


app.controller(
    'ChartsController',
    [
        '$scope',
        '$http',
        '$location',
        '$compile',
        'ChartPanel',
        'DATA',
        ChartsController
    ]
);

app.directive('sliderRange', ['$document', ChartSlider]);
