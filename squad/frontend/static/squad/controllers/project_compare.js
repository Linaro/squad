export function ProjectCompareController($scope, attach_select2) {
    $scope.init = function() {
        if($('#group-select').length) {
            attach_select2('/api/groups/', $('#group-select'), 'slug', function(term){
                return {'filters': '%28name__icontains%253D' + term +
                       '%29%20%7C%20%28slug__icontains%253D' + term + '%29'}
            })
        }
    }
}
