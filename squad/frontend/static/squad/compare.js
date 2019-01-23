import {CompareController} from './controllers/compare.js'

var app = angular.module('SquadCompare', []);

appConfig(app, ['locationProvider']);

app.controller(
    'CompareController',
    [
        '$scope',
        '$http',
        '$location',
        CompareController
    ]
);
