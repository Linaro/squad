export function BuildListCompareController($scope, $window) {
    $scope.baseline_build = ''
    $scope.target_build = ''
    $scope.compareBuilds = function(project) {
        var baseline = $scope.baseline_build
        var target = $scope.target_build
        if(baseline == '' || target == '') {
            alert($scope.invalid_number_of_builds_msg)
        }
        else if(baseline == target) {
            alert($scope.invalid_selected_builds_msg)
        }
        else {
            var path = '/_/comparebuilds/?project=' + project
            path += '&baseline=' + baseline
            path += '&target=' + target
            $window.location.href = path
        }
    }

    $scope.show_target_radio = function(target){
        var baseline = $scope.baseline_build
        return baseline != '' && baseline != target
    }
}
