export function BuildCompareController($scope, attach_select2) {
    $scope.init = function(project_id) {
        if($('#project-select').length) {
            attach_select2('/api/projects/', $('#project-select'), 'full_name', function(term){
                return {'filters': '%28full_name%253D' + term +
                       '%29%20%7C%20%28group__name__icontains%253D' + term +
                       '%29%20%7C%20%28name__icontains%253D' + term +
                       '%29%20%7C%20%28slug__icontains%253D' + term + '%29'}
            })
        }

        if($('#baseline-select').length) {
            attach_select2('/api/builds/', $('#baseline-select'), 'version', function(term){
                return {'project__id': project_id, 'version__startswith': term}
            })
        }

        if($('#target-select').length) {
            attach_select2('/api/builds/', $('#target-select'), 'version', function(term){
                return {'project__id': project_id, 'version__startswith': term}
            })
        }
    }
}
