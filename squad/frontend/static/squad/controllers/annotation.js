export function AnnotationController($scope, $http, $httpParamSerializerJQLike) {
    $scope.updateAnnotation = function(build_id) {
        var method = 'post'
        var url = '/api/annotations/'
        var data = {
            description: $scope.description,
            build: build_id
        }
        if (typeof $scope.annotation_id !== "undefined") {
            method = "put"
            url += $scope.annotation_id + "/"
            data["id"] = $scope.annotation_id
        }
        $http({
            method: method,
            url: url,
            data: $httpParamSerializerJQLike(data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'}
        }).then(function(response) {
            $("#annotation_text").html("<strong>Annotation: </strong>" +
                                       $scope.description)
            $("#annotation_text").removeClass("hidden")
            $("#annotation_button").html("Update")
            $("#annotation_modal").modal('hide')
            $scope.annotation_id = response.data.id
        }, function(response) {
            var msg = "There was an error while editing annotation."
            if (response.data) {
                msg += "\nMessage: " + response.data.detail
            }
            alert(msg)
        })
    }
}
