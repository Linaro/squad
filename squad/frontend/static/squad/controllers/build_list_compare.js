export function BuildListCompareController($scope, $window) {
    $scope.baseline_build = ''
    $scope.target_build = ''
    $scope.comparison_type = ''
    $scope.compareBuilds = function(project) {
        var baseline = $scope.baseline_build
        var target = $scope.target_build
        var comparison_type = $scope.comparison_type
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
            path += '&comparison_type=' + comparison_type
            $window.location.href = path
        }
    }

    $scope.show_target_radio = function(target){
        var baseline = $scope.baseline_build
        return baseline != '' && baseline != target
    }
}
