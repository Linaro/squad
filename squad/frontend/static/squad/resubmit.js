var app = angular.module('SquadResubmit', []);

function ResubmitController($scope, $http, $location, $timeout) {

    $scope.loading = false
    $scope.done = false
    $scope.resubmit = function(test_job_id) {
        if ($scope.done) return
        $scope.loading = true

        $http.get("/api/resubmit/" + test_job_id).then(
            function() {
                $scope.loading = false
                $scope.done = true
            }
        )

        $timeout(function() {
            $scope.loading = false
            $scope.done = true
        }, 2000).apply();

    }

    $scope.forceresubmit = function(test_job_id) {
        if ($scope.done) return
        $scope.loading = true

        $http.get("/api/forceresubmit/" + test_job_id).then(
            function() {
                $scope.loading = false
                $scope.done = true
            }
        )

        $timeout(function() {
            $scope.loading = false
            $scope.done = true
        }, 2000).apply();

    }

}

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
