var app = angular.module('Filter', []);

var URL = {}

function FilterController($scope, $attrs, $location) {
  $scope.match = function(id) {
    var filter = $scope.filter
    var visible
    if (filter && filter.trim().filter != "") {
      element = document.getElementById(id)
      visible = element.textContent.match(filter) != null
    } else {
      visible = true
    }
    return visible
  }

  $scope.details_visible = {}
  $scope.toggle_details = function(id) {
    var element = document.getElementById(id)
    if ($scope.details_visible[id]) {
      delete $scope.details_visible[id]
    } else {
      $scope.details_visible[id] = true
    }
    $scope.update()
    return false
  }

  $scope.update = function() {
    URL[$attrs.param] = $scope.filter
    URL.details = _.sortBy(_.map($scope.details_visible, function(v, k) {
      return k.replace('details-', '')
    })).join(',')
    $location.search(URL)
  }

  $scope.init = function() {
    var params = $location.search()
    $scope.filter = params[$attrs.param]
    if (params.details) {
      _.each(params.details.split(','), function(d) {
        $scope.details_visible["details-" + d] = true
      })
    }
  }

  $scope.init()
}

app.controller(
    'FilterController',
    [
        '$scope',
        '$attrs',
        '$location',
        FilterController
    ]
)
