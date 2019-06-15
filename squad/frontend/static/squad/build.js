import {AnnotationController} from './controllers/annotation.js'
import {BuildCompareController} from './controllers/build_compare.js'
import {FilterController} from './controllers/filter.js'
import {ResubmitController} from './controllers/resubmit.js'
import {Config as appConfig} from './config.js'
import {attach_select2} from './attach_select2.js'

var app = angular.module('Build', []);

appConfig(app, ['httpProvider']);

app.value('build', window.build);
app.factory('attach_select2', ['$http', attach_select2]);

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

app.controller(
    'BuildCompareController',
    [
        '$scope',
        'attach_select2',
        BuildCompareController
    ]
);
