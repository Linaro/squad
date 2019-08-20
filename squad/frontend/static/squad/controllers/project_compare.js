export function ProjectCompareController($scope, attach_select2) {
    $scope.init = function() {
        if($('#group-select').length) {
            attach_select2('/api/groups/', $('#group-select'), 'slug', function(term){
                return {'filters': '%28name__icontains%253D' + term +
                       '%29%20%7C%20%28slug__icontains%253D' + term + '%29'}
            })
        }
    }

    // projects is in the form of [project_id] => true/false
    // where true == checked, and false == not checked
    $scope.projects = {}

    $scope.attachSelect2 = function(elemId, project_id) {
        var elem = $('#' + elemId)
        attach_select2('/api/builds/', elem, 'version', function(term){
            return {'project__id': project_id, 'version__startswith': term}
        })
    }

    $scope.submit = function() {
        var selected_builds = {}
        for(var project_id in $scope.projects) {
            if($scope.projects[project_id]) {
                let key = 'project_' + project_id
                selected_builds[key] = $('select[name=' + key + ']').val()
            }
        }
        window.location = window.location.search + '&' + $.param(selected_builds)
    }
}
