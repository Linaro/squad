import {BuildListCompareController} from './controllers/build_list_compare.js'
import {Config as appConfig} from './config.js'

var app = angular.module('BuildList', []);

app.controller(
    'BuildListCompareController',
    [
        '$scope',
        '$window',
        BuildListCompareController
    ]
)
