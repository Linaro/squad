function ThresholdResource($resource) {
    return $resource('/api/metricthresholds/:id/', {id: '@id'},
                     {
                         'query': {
                             method: 'GET',
                             url: '/api/metricthresholds/',
                             isArray: false
                         },
                         'update': {
                             method: 'PUT',
                             url: '/api/metricthresholds/:id/',
                             params:  {
                                 id: '@id'
                             }
                         }
                     }, {
                         stripTrailingSlashes: false
                     }
    )
}

function getKeyByValue(object, value) {
    return Object.keys(object).find(key => object[key] === value);
}

function MetricThresholdController($scope, Threshold) {
    $scope.openNewThresholdModal = function() {
        $scope.currentThreshold = new Threshold()
        $scope.currentThreshold.environment = 'all'
    }

    $scope.initMetricThresholds = function() {
        // Initialize threshold for modal dialog.
        $scope.currentThreshold = new Threshold()
        $scope.currentThreshold.environment = 'all'
        //  Get thresholds from the backend.
        Threshold.query({project: $scope.project}).$promise.then(
            function(data) {
                $scope.thresholds = data.results
                for (var i in $scope.thresholds) {
                    var threshold = $scope.thresholds[i]
                    threshold.project = $scope.project
                    if (threshold.environment == null) {
                        threshold.environment = 'all'
                    } else {
                        threshold.environment = $scope.environments[threshold.environment.slice(0,-1).split("/").pop()]
                    }
                }
            }
        )
    }

    $scope.updateMetricThreshold = function() {
        // Add/update the current threshold from modal dialog.
        var savedThreshold = null
        var threshold_index = $scope.currentThreshold.index
        // save env name to reset to name value later in modal
        var env_name = $scope.currentThreshold.environment
        // Project is always mandatory
        $scope.currentThreshold.project = "/api/projects/" + $scope.project + "/"
        // get env id/key using its name/value
        var currentEnvironment = $scope.currentThreshold.environment

        if ($scope.currentThreshold.environment == "all" || $scope.currentThreshold.environment == null) {
            delete $scope.currentThreshold.environment
        } else {
            $scope.currentThreshold.environment = "/api/environments/" + getKeyByValue($scope.environments, $scope.currentThreshold.environment) + "/"
        }
        if ($scope.currentThreshold.id) {
            savedThreshold = $scope.currentThreshold.$update().then(
                function(response) {
                    $scope.currentThreshold.environment = env_name
                    $.extend($scope.thresholds[threshold_index],
                             $scope.currentThreshold)
                })
        } else {
            savedThreshold = $scope.currentThreshold.$save().then(
                function(response) {
                    $scope.currentThreshold.environment = env_name
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
            $scope.currentThreshold.environment = currentEnvironment
        })
    }

    $scope.removeThreshold = function(threshold) {
        // Delete threshold.
        Threshold.delete({id: threshold.id}).$promise.then(function(response) {
            var index = $scope.thresholds.indexOf(threshold)
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
    })

    $scope.modalClosed = function() {
        // Reset threshold in modal dialog.
        $scope.currentThreshold = new Threshold()
        $scope.errors = null
    }
}

export {
    MetricThresholdController,
    ThresholdResource
}
