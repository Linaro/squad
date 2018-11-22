var app = angular.module('Build', []);

var URL = {}

function AnnotationController($scope, $http, $httpParamSerializerJQLike) {
    $scope.updateAnnotation = function(build_id) {
        var method = 'post'
        var url = '/api/annotations/'
        var data = {
            description: $scope.description,
            build: build_id
        }
        if (typeof $scope.annotation_id !== "undefined") {
            method = "put"
            url += $scope.annotation_id + "/"
            data["id"] = $scope.annotation_id
        }
        $http({
            method: method,
            url: url,
            data: $httpParamSerializerJQLike(data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded',
                      'X-CSRFTOKEN': csrf_token}
        }).then(function(response) {
            $("#annotation_text").html("<strong>Annotation: </strong>" +
                                       $scope.description)
            $("#annotation_text").removeClass("hidden")
            $("#annotation_button").html("Update")
            $("#annotation_modal").modal('hide')
            $scope.annotation_id = response.data.id
        }, function(response) {
            var msg = "There was an error while editing annotation."
            if (response.data) {
                msg += "\nMessage: " + response.data.description
            }
            alert(msg)
        })
    }
}

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

function ResubmitController($scope, $http, $location, $timeout) {

    $scope.error = false
    $scope.loading = false
    $scope.done = false
    $scope.resubmit = function(test_job_id, force) {
        if ($scope.done) return
        $scope.loading = true

        var endpoint = force ? "/api/forceresubmit/" : "/api/resubmit/";

        $http.get(endpoint + test_job_id).then(
            function(response) {
                $timeout(function() {
                    $scope.loading = false
                    $scope.done = true
                }, 1000)
            },
            function(response) {
                var msg = "There was an error while resubmitting.\n" +
                    "Status = " + response.status + " " + response.statusText +
                    "(" + response.xhrStatus + ")"
                alert(msg)
                $scope.loading = false
                $scope.error = true
                $scope.done = true
            }
        )
    }
}

app.controller(
    'AnnotationController',
    [
        '$scope',
        '$http',
        '$httpParamSerializerJQLike',
        AnnotationController
    ]
)

app.controller(
    'FilterController',
    [
        '$scope',
        '$attrs',
        '$location',
        FilterController
    ]
)

app.controller(
    'ResubmitController',
    [
        '$scope',
        '$http',
        '$location',
        '$timeout',
        ResubmitController
    ]
);
