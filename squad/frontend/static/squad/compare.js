var app = angular.module('SquadCompare', []);

app.config(['$locationProvider', function($locationProvider) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    })
}])

function CompareController($scope, $http, $location) {

    $scope.updateKnownIssue = function() {
        if ($scope.selectedSuite != undefined && $scope.selectedTest != undefined) {
            $http.get('/api/knownissues', {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, 'active': true}})
                .then(function(response) {
                    if (response.data.count > 0){
                        $scope.hasKnownIssue = true;
                        $scope.knownIssues = response.data.results;
                    } else {
                        $scope.hasKnownIssue = false;
                        $scope.knownIssue = undefined
                    }
                })
        } else {
            $scope.hasKnownIssue = false;
            $scope.knownIssue = undefined;
        }
    }

    $scope.updateURL = function() {
        var search_params = {
            project: $scope.getProjectIds(),
        }
        if ($scope.selectedSuite != undefined) {
            search_params['suite'] = $scope.selectedSuite;
        }
        if ($scope.selectedTest != undefined) {
            search_params['test'] = $scope.selectedTest;
        }
        $location.search(search_params);
    }

    $scope.getProjectIds = function() {
        return _.map($scope.selectedProjects, function(pr) {return pr.id})
    }

    $scope.projectSearchUpdate = function(project_list) {
        if ($scope.projectSearchResponses > 0) {
            for (var i = 0; i < project_list.length; i++) {
                var existing = _.find($scope.projects, function(m) {
                    return m.id == project_list[i].id;
                })
                if (!existing) {
                    $scope.projects.push(project_list[i])
                }
            }
        } else {
            $scope.projects = project_list;
        }
        $scope.projectSearchResponses += 1;
        $('#projects-dropdown').collapse('show');
        $('#suites-dropdown').collapse('hide');
        $('#tests-dropdown').collapse('hide');
    }

    $scope.doProjectSearch = function() {
        var params = new Array();
        params['name__startswith'] = $scope.project;
        $scope.projectSearchResponses = 0;
        $http.get('/api/projects', {params: params})
        .then(function(response) {
            $scope.projectSearchUpdate(response.data.results);
        });
        var params2 = new Array();
        params2['slug__startswith'] = $scope.project;
        $http.get('/api/projects', {params: params2})
        .then(function(response) {
            $scope.projectSearchUpdate(response.data.results);
        });
    }

    $scope.addProject = function(project) {
        var existing = _.find($scope.selectedProjects, function(m) {
            return m.id == project.id;
        })
        if (!existing) {
            $scope.selectedProjects.push(project)
            $scope.showProgress[project.id] = true;
        }
        $scope.project = undefined;
        if ($scope.selectedTest && $scope.selectedSuite) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
        $('#projects-dropdown').collapse('hide');
    }

    $scope.removeProject = function(project) {
        _.remove($scope.selectedProjects, function(m) {
            return m.id == project.id
        })
        if ($scope.selectedProjects.length == 0) {
            $scope.showResults = false;
        }
        $scope.updateURL();
    }

    $scope.doSuiteSearch = function() {
        var params = new Array();
        params['slug__startswith'] = $scope.suite;
        var projectSlugList = new Array();
        if ($scope.selectedProjects.length > 0) {
            for (var i=0; i<$scope.selectedProjects.length; i++) {
                projectSlugList.push($scope.selectedProjects[i].slug)
            }
            params['project__slug__in'] = projectSlugList.join();
        }
        $http.get('/api/suites/', {params: params})
        .then(function(response) {
            $scope.suites = [...new Set(response.data.results.map(item => item.slug))];
            $('#suites-dropdown').collapse('show');
            $('#projects-dropdown').collapse('hide');
            $('#tests-dropdown').collapse('hide');
        });
    }

    $scope.addSuite = function(suite) {
        if ($scope.selectedSuite != suite) {
            $scope.removeTest();
        }
        $scope.selectedSuite = suite;
        $scope.suite = undefined;
        if ($scope.selectedTest && $scope.selectedProjects.length > 0) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
        $('#suites-dropdown').collapse('hide');
    }

    $scope.removeSuite = function() {
        $scope.selectedSuite = undefined;
        $scope.selectedTest = undefined;
        $scope.showResults = false;
        $scope.updateURL();
        $scope.updateKnownIssue();
    }

    $scope.doTestSearch = function() {
        var params = new Array();
        params['name__startswith'] = $scope.test;
        var projectSlugList = new Array();
        if ($scope.selectedProjects.length > 0) {
            for (var i=0; i<$scope.selectedProjects.length; i++) {
                projectSlugList.push($scope.selectedProjects[i].slug)
            }
            params['test_run__build__project__slug__in'] = projectSlugList.join();
        }
        params['suite__slug'] = $scope.selectedSuite;

        $http.get('/api/tests/', {params: params})
        .then(function(response) {
            $scope.tests = [...new Set(response.data.results.map(item => item.short_name))];
            $('#tests-dropdown').collapse('show');
            $('#suites-dropdown').collapse('hide');
            $('#projects-dropdown').collapse('hide');
        });
    }

    $scope.addTest = function(test) {
        $scope.selectedTest = test;
        $scope.test = undefined;
        if ($scope.selectedSuite && $scope.selectedProjects.length > 0) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
        $('#tests-dropdown').collapse('hide');
    }

    $scope.removeTest = function() {
        $scope.selectedTest = undefined;
        $scope.showResults = false;
        $scope.updateURL();
        $scope.updateKnownIssue();
    }

    $scope.doCompare = function() {
        // get the list of builds for each project
        for (i=0; i<$scope.selectedProjects.length; i++) {
            (function(index){
                $http.get($scope.selectedProjects[index].url + "test_results/", {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, "limit": 10}})
                    .then(function(response){
                        $scope.projectBuilds[$scope.selectedProjects[index].id] = response.data;
                        if (response.data.length > 0) {
                            $scope.projectEnvironments[$scope.selectedProjects[index].id] = response.data[0].environments;
                        } else {
                            $scope.projectEnvironments[$scope.selectedProjects[index].id] = new Array();
                        }
                        $scope.showProgress[$scope.selectedProjects[index].id] = false;
                        $scope.loadedLimits[$scope.selectedProjects[index].id] = 10;
                    });
            })(i);
        }
        $scope.updateKnownIssue();
    }

    $scope.loadMoreData = function(project_id) {
        loadedLimit = $scope.loadedLimits[project_id];
        $scope.showProgress[project_id] = true;
        (function(id){
            index = $scope.selectedProjects.findIndex(x => x.id == id);
            $http.get($scope.selectedProjects[index].url  + "test_results/", {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, "limit": 10, "offset": loadedLimit}})
                .then(function(response) {
                    $scope.projectBuilds[id] = $scope.projectBuilds[id].concat(response.data);
                    $scope.loadedLimits[id] += 10;
                    $scope.showProgress[id] = false;
                });
        })(project_id);
    }

    var params = $location.search();
    var project_list = new Array();
    if (params.project instanceof Array) {
        project_list = params.project;
    } else {
        project_list.push(params.project);
    }
    $scope.selectedProjects = new Array();
    $scope.showProgress = new Array();
    $scope.loadedLimits = new Array();
    $scope.showResults = false;
    $scope.hasKnownIssue = false;
    $scope.projectSearchResponses = 0;
	$http.get('/api/projects', {params: {'id__in': project_list.join()}}).then(function(response) {
		$scope.projects = response.data.results;
        $scope.selectedProjects = _.filter($scope.projects, function(project) {
            var found = _.find(_.castArray(params.project), function(param) {
                if (param == project.id) {
                    return param
                }
            })
            return found
        })
        for (var i = 0; i < $scope.selectedProjects.length; i++) {
            $scope.showProgress[$scope.selectedProjects[i].id] = true;
        }
        if ($scope.selectedSuite && $scope.selectedTest && $scope.selectedProjects.length > 0) {
            $scope.showResults = true;
            $scope.doCompare();
        }
	});

    $scope.selectedSuite = params.suite;
    $scope.selectedTest = params.test;

    $scope.updateKnownIssue();

    $scope.projectBuilds = new Array();
    $scope.projectEnvironments = new Array();
}

app.controller(
    'CompareController',
    [
        '$scope',
        '$http',
        '$location',
        CompareController
    ]
);

