export function ResubmitController($scope, $http, $location, $timeout) {

    $scope.error = false
    $scope.loading = false
    $scope.done = false
    $scope.resubmit = function(test_job_id, force) {
        if ($scope.done) return
        $scope.loading = true

        var endpoint = force ? "/api/forceresubmit/" : "/api/resubmit/";

        $http.post(endpoint + test_job_id).then(
            function(response) {
                $timeout(function() {
                    $scope.loading = false
                    $scope.done = true
                }, 1000)
            },
            function(response) {
                var msg = "There was an error while resubmitting.\n" +
                    "Status = " + response.status + " " + response.statusText +
                    "(" + response.xhrStatus + ")"
                alert(msg)
                $scope.loading = false
                $scope.error = true
                $scope.done = true
            }
        )
    }
}
