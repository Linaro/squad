import {ThresholdResource, MetricThresholdController} from './controllers/metricThreshold.js'

var app = angular.module('MetricThreshold', ['ngResource']);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

app.config(['$httpProvider', function($httpProvider) {
    $httpProvider.defaults.headers.common['X-CSRFToken'] = csrf_token
    $httpProvider.defaults.headers.common['Content-Type'] = 'application/x-www-form-urlencoded'
}])

app.factory('Threshold', ThresholdResource)

app.controller(
    'MetricThresholdController',
    [
        '$scope',
        '$http',
        'Threshold',
        '$httpParamSerializerJQLike',
        MetricThresholdController
    ]
);
