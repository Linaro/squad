export function BuildReleaseController($scope, $http, $httpParamSerializerJQLike) {
    $scope.updateRelease = function(build_url) {
        $http({
            method: 'get',
            url: build_url
        }).then(function(response) {
            var data = response.data
            data.is_release = $scope.is_release
            data.release_label = $scope.release_label
            $http({
                method: 'put',
                url: build_url,
                data: $httpParamSerializerJQLike(data),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            }).then(function(response) {
                if ($scope.is_release) {
                    $("#release_text").html("<i class='fa fa-tag'></i> <strong>Release: </strong>" +
                                               $scope.release_label)
                    $("#release_text").removeClass("hidden")
                    $("#release_button").html("Update")
                    $("#release_modal").modal('hide')
                } else {
                    $("#release_text").html("")
                    $("#release_text").addClass("hidden")
                    $("#release_button").html("Mark release")
                    $("#release_modal").modal('hide')
                }
            }, function(response) {
                var msg = "There was an error while editing build."
                if (response.data) {
                    msg += "\nMessage: " + response.data.detail
                }
                alert(msg)
            })
        })
    }
}

