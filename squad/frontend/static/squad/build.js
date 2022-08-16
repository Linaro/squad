import {AnnotationController} from './controllers/annotation.js'
import {BuildCompareController} from './controllers/build_compare.js'
import {BuildReleaseController} from './controllers/build_release.js'
import {FilterController} from './controllers/filter.js'
import {ResubmitController} from './controllers/resubmit.js'
import {CancelController} from './controllers/cancel.js'
import {FetchController} from './controllers/fetch.js'
import {TestJobsProgressController} from './controllers/testjobs_progress.js'
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
    'BuildReleaseController',
    [
        '$scope',
        '$http',
        '$httpParamSerializerJQLike',
        BuildReleaseController
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
    'CancelController',
    [
        '$scope',
        '$http',
        '$location',
        '$timeout',
        CancelController
    ]
);

app.controller(
    'FetchController',
    [
        '$scope',
        '$http',
        '$timeout',
        FetchController
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

app.controller(
    'TestJobsProgressController',
    [
        '$scope',
        '$http',
        TestJobsProgressController
    ]
);
