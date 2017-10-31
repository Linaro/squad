var app = angular.module('Filter', []);

var URL = {}

function FilterController($scope, $attrs, $location) {
  $scope.visibility = {}
  $scope.match = function(id) {
    var filter = $scope.filter
    var visible
    if (filter && filter.trim().filter != "") {
      element = document.getElementById(id)
      visible = element.textContent.match(filter) != null
    } else {
      visible = true
    }
    $scope.visibility[id] = visible
    $scope.update()
    return visible
  }

  $scope.count_visible = function(always_visible) {
    return Math.max(0, _.filter($scope.visibility).length - always_visible)
  }

  $scope.update = function() {
    var search_update = {}
    URL[$attrs.param] = $scope.filter
    $location.search(URL)
  }

  $scope.init = function() {
    var params = $location.search()
    $scope.filter = params[$attrs.param]
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
