import {ProjectCompareController} from './controllers/project_compare.js'
import {attach_select2} from './attach_select2.js'
import {Config as appConfig} from './config.js'

var app = angular.module('ProjectCompare', []);

appConfig(app, ['httpProvider']);

app.factory('attach_select2', ['$http', attach_select2]);

app.controller(
    'ProjectCompareController',
    [
        '$scope',
        'attach_select2',
        ProjectCompareController
    ]
);

