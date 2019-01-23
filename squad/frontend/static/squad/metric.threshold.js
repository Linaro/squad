import {ThresholdResource, MetricThresholdController} from './controllers/metricThreshold.js'
import {Config as appConfig} from './config.js'

var app = angular.module('MetricThreshold', ['ngResource']);

appConfig(app, ['locationProvider', 'httpProvider']);

app.factory('Threshold', ThresholdResource)

app.controller(
    'MetricThresholdController',
    [
        '$scope',
        'Threshold',
        MetricThresholdController
    ]
);
