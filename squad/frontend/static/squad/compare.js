import {CompareController} from './controllers/compare.js'
import {Config as appConfig} from './config.js'

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
