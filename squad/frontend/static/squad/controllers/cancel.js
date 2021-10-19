export function CancelController($scope, $http, $location, $timeout) {

    $scope.error = false
    $scope.loading = false
    $scope.done = false
    $scope.cancel = function(test_job_id) {
        if ($scope.done) return
        $scope.loading = true

        $http.post("/api/testjobs/" + test_job_id + "/cancel/").then(
            function(response) {
                $timeout(function() {
                    $scope.loading = false
                    $scope.done = true
                }, 1000)
            },
            function(response) {
                var msg = "There was an error while cancelling.\n" +
                    "Status = " + response.status + " " + response.statusText +
                    "(" + response.xhrStatus + ")"
                alert(msg)
                $scope.loading = false
                $scope.error = true
                $scope.done = true
            }
        )
    }

    $scope.cancel_all = function(build_id) {
        if ($scope.done) return
        $scope.loading = true

        $http.post("/api/builds/" + build_id + "/cancel/").then(
            function(response) {
                $timeout(function() {
                    $scope.loading = false
                    $scope.done = true
                }, 1000)
                alert(response.data['status'])
            },
            function(response) {
                var msg = "There was an error while cancelling.\n" +
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
