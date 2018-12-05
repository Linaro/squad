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

app.factory('Threshold', function($resource) {
    return $resource('/api/metricthresholds/:id/', {id: '@id'},
                     {
                         'query': {
                             method: 'GET',
                             isArray: false
                         },
                         'update': {
                             method: 'PUT'
                         }
                     }, {
                         stripTrailingSlashes: false
                     }
    )
})

function MetricThresholdController($scope, $http, Threshold, $httpParamSerializerJQLike) {

    $scope.initMetricThresholds = function() {
        // Initialize threshold for modal dialog.
        $scope.currentThreshold = new Threshold()

        //  Get thresholds from the backend.
        Threshold.query({project: $scope.project}).$promise.then(
            function(data) {
                $scope.thresholds = data.results
            }
        )
    }

    $scope.updateMetricThreshold = function() {
        // Add/update the current threshold from modal dialog.
        var savedThreshold = null
        var threshold_index = $scope.currentThreshold.index
        $scope.currentThreshold.project = "/api/projects/" + $scope.project + "/"

        if ($scope.currentThreshold.id) {
            savedThreshold = $scope.currentThreshold.$update().then(
                function(response) {
                    $.extend($scope.thresholds[threshold_index],
                             $scope.currentThreshold)
                })
        } else {
            savedThreshold = $scope.currentThreshold.$save().then(
                function(response) {
                    $scope.thresholds.push(response)
                })
        }

        savedThreshold.then(function() {
            // Reset threshold in modal dialog.
            $scope.currentThreshold = new Threshold()
        }).then(function() {
            $scope.errors = null
            $("#threshold_modal").modal('hide')
        }, function(error) {
            $scope.errors = error.data
        })
    }

    $scope.removeThreshold = function(threshold) {
        // Delete threshold.
        Threshold.delete({id: threshold.id}).$promise.then(function(response) {
            index = $scope.thresholds.indexOf(threshold)
            $scope.thresholds.splice(index, 1)
        })
    }

    $scope.setThreshold = function(threshold) {
        // Set the fields in the modal dialog prior to updating threshold.
        $.extend($scope.currentThreshold, threshold)
        $scope.currentThreshold.index = $scope.thresholds.indexOf(threshold)
    }

    $scope.$watch('$viewContentLoaded', function () {
        $scope.initMetricThresholds()
    });
}

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
