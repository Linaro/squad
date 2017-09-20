var app = angular.module('ProjectList', []);

function DescriptionController($scope) {
    $scope.index = 0
    $scope.init = function(id) {
        $scope.text = document.getElementById("short-description-" + id)

        var fulldesc = document.getElementById("full-description-" + id).innerHTML
        var shortdesc = $scope.text.innerHTML
        $scope.descriptions = [shortdesc, fulldesc]

        $scope.button = document.getElementById('toggle-description-' + id)
        if ($scope.button) {
            $scope.button_titles = [$scope.button.innerHTML, $scope.button.getAttribute('data-alt-title')]
        }
    }

    $scope.toggle = function() {
        console.log($scope.index)
        $scope.index = ($scope.index + 1) % 2;
        console.log($scope.index)
        $scope.text.innerHTML = $scope.descriptions[$scope.index]
        $scope.button.innerHTML = $scope.button_titles[$scope.index]
    }
}

app.controller(
    'DescriptionController',
    [
        '$scope',
        DescriptionController
    ]
);


