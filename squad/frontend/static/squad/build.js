import {AnnotationController} from './controllers/annotation.js'
import {FilterController} from './controllers/filter.js'
import {ResubmitController} from './controllers/resubmit.js'
import {Config as appConfig} from './config.js'

var app = angular.module('Build', []);

appConfig(app, ['httpProvider']);

app.controller(
    'AnnotationController',
    [
        '$scope',
        '$http',
        '$httpParamSerializerJQLike',
        AnnotationController
    ]
)

app.controller(
    'FilterController',
    [
        '$scope',
        '$attrs',
        '$location',
        FilterController
    ]
)

app.controller(
    'ResubmitController',
    [
        '$scope',
        '$http',
        '$location',
        '$timeout',
        ResubmitController
    ]
);
