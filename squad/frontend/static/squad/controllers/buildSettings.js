export function BuildSettingsController($scope, $http, build) {
    $scope.build = build

    var alertBox = $('#build-settings-alert')

    $scope.updateBuild = function() {
        var method = 'patch'
        var url = '/api/builds/' + $scope.build.id + '/'
        var data = {
            keep_data: $scope.keep_data,
        }
        $http({
            method: method,
            url: url,
            data: data
        }).then(function(response) {
            $scope.form_changed = false
            $scope.build = response.data // returns saved build

            $scope.alert_type = 'success'
            $scope.alert_message = 'Build settings saved successfully!'
            alertBox.show()
            setTimeout(function(){alertBox.fadeOut(500)}, 3000)
        }, function(response) {
            var errors = ''
            response.data['keep_data'].forEach(function(el) {
                errors += el.toLowerCase() + ' '
            })

            var error_msg = 'Keep data (' + errors + ')'
            $scope.alert_type = 'danger'
            $scope.alert_message = 'Could not save settings: ' + error_msg
            alertBox.show()
        })
    }

    $scope.init = function(){
        $scope.keep_data = $scope.build.keep_data
        alertBox.hide()
    }

    $scope.$watch('keep_data', function() {
        $scope.form_changed = ($scope.keep_data != $scope.build.keep_data)
    });

    $scope.init()
}
