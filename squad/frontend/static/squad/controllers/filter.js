export function FilterController($scope, $attrs, $location) {
  $scope.match = function(id) {
    var filter = $scope.filter
    var visible
    var element
    if (filter && filter.trim().filter != "") {
      element = document.getElementById(id)
      if (element != null) {
        visible = element.textContent.match(filter) != null
      }
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

  $scope.URL = {}
  $scope.update = function() {
    $scope.URL[$attrs.param] = $scope.filter
    $scope.URL.details = _.sortBy(_.map($scope.details_visible, function(v, k) {
      return k.replace('details-', '')
    })).join(',')
    $location.search($scope.URL)
  }

  $scope.attachments_visibility = {}
  $scope.selected_attachment = {}
  $scope.show_download_button = function(changing_key){
      for (var key in $scope.attachments_visibility){
          for (var attachment_file in $scope.attachments_visibility[key]){
              $scope.attachments_visibility[key][attachment_file] = false;
          }
      }
      $scope.attachments_visibility[changing_key][$scope.selected_attachment[changing_key]] = true;
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
