export function FetchController($scope, $http, $timeout) {

    $scope.error = false
    $scope.loading = false
    $scope.done = false
    $scope.fetch = function(test_job_id) {
        if ($scope.done) return
        $scope.loading = true

        $http.post("/api/testjobs/" + test_job_id + "/fetch/").then(
            function(response) {
                $timeout(function() {
                    $scope.loading = false
                    $scope.done = true
                }, 1000)
            },
            function(response) {
                var msg = "There was an error while fetching.\n" +
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
